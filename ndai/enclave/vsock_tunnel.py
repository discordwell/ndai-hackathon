"""Parent-side TCP tunnel for enclave TLS traffic.

Replaces the JSON LLM proxy for Nitro mode. Instead of deserializing and
re-serializing LLM requests (which exposes plaintext to the parent), this
tunnel forwards raw bytes between the enclave's vsock and a remote TCP host.

The enclave performs the TLS handshake itself, so the parent only sees
encrypted ciphertext.

Protocol:
    1. Enclave connects to parent on vsock TUNNEL_PORT
    2. Enclave sends: "CONNECT host:port\n" (text line)
    3. Parent validates host:port against whitelist
    4. Parent opens TCP connection to host:port
    5. Parent sends: "OK\n" (or "DENIED\n" / "ERROR ...\n")
    6. Bidirectional byte forwarding until either side closes

Only whitelisted hosts are allowed to prevent misuse.
"""

import asyncio
import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

# vsock constants
AF_VSOCK = 40
VMADDR_CID_ANY = 0xFFFFFFFF
TUNNEL_PORT = 5002  # Distinct from command (5000) and LLM proxy (5001)

# Allowed destinations — only LLM API endpoints
ALLOWED_HOSTS: set[tuple[str, int]] = {
    ("api.openai.com", 443),
    ("api.anthropic.com", 443),
}

# Buffer size for bidirectional forwarding
TUNNEL_BUFFER_SIZE = 65536

# Maximum concurrent tunnel connections
MAX_CONCURRENT_TUNNELS = 16


class TunnelError(Exception):
    """Error in tunnel operation."""


class VsockTunnel:
    """Parent-side TCP tunnel that forwards enclave vsock traffic to allowed hosts.

    The enclave initiates a CONNECT request specifying the target host:port.
    The tunnel validates against the whitelist, opens a TCP connection, and
    then blindly forwards bytes in both directions.

    Usage:
        tunnel = VsockTunnel()
        await tunnel.run()  # blocks, serving tunnel requests
        # or
        task = await tunnel.run_background()  # returns asyncio.Task
    """

    def __init__(
        self,
        port: int = TUNNEL_PORT,
        allowed_hosts: set[tuple[str, int]] | None = None,
        max_concurrent: int = MAX_CONCURRENT_TUNNELS,
    ):
        self.port = port
        self.allowed_hosts = allowed_hosts or ALLOWED_HOSTS
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._server_sock: socket.socket | None = None
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._bytes_forwarded = 0

    async def run(self) -> None:
        """Start the tunnel and serve connections until stopped."""
        self._server_sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((VMADDR_CID_ANY, self.port))
        self._server_sock.listen(self.max_concurrent)
        self._server_sock.setblocking(False)
        self._running = True

        logger.info(
            "VsockTunnel listening on vsock port %d (allowed: %s)",
            self.port,
            ", ".join(f"{h}:{p}" for h, p in self.allowed_hosts),
        )

        loop = asyncio.get_event_loop()
        try:
            while self._running:
                try:
                    conn, addr = await loop.run_in_executor(
                        None, self._accept_with_timeout
                    )
                except TimeoutError:
                    continue

                logger.info("Tunnel: accepted connection from CID=%s port=%s", *addr)
                task = asyncio.create_task(self._handle_connection(conn, addr))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            await self._cleanup()

    async def run_background(self) -> asyncio.Task:
        """Start the tunnel as a background asyncio task."""
        task = asyncio.create_task(self.run())
        await asyncio.sleep(0.05)
        return task

    async def stop(self) -> None:
        """Gracefully stop the tunnel."""
        logger.info("Stopping VsockTunnel (forwarded %d bytes total)", self._bytes_forwarded)
        self._running = False
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=30)
        await self._cleanup()

    @property
    def bytes_forwarded(self) -> int:
        """Total bytes forwarded through the tunnel."""
        return self._bytes_forwarded

    def _accept_with_timeout(self) -> tuple[socket.socket, tuple[int, int]]:
        """Accept with 1-second timeout for run loop check."""
        assert self._server_sock is not None
        self._server_sock.settimeout(1.0)
        try:
            return self._server_sock.accept()
        except socket.timeout as exc:
            raise TimeoutError from exc

    async def _handle_connection(
        self,
        vsock_conn: socket.socket,
        addr: tuple[int, int],
    ) -> None:
        """Handle a single tunnel connection.

        1. Read CONNECT line
        2. Validate against whitelist
        3. Open TCP connection
        4. Forward bytes bidirectionally
        """
        vsock_conn.setblocking(True)
        vsock_conn.settimeout(30)  # 30s for CONNECT handshake
        tcp_sock: socket.socket | None = None

        try:
            async with self._semaphore:
                loop = asyncio.get_event_loop()

                # Read CONNECT line
                connect_line = await loop.run_in_executor(
                    None, self._read_connect_line, vsock_conn
                )

                host, port = self._parse_connect(connect_line)

                if (host, port) not in self.allowed_hosts:
                    logger.warning("Tunnel: denied connection to %s:%d", host, port)
                    await loop.run_in_executor(
                        None, vsock_conn.sendall, b"DENIED\n"
                    )
                    return

                # Open TCP connection to target
                try:
                    tcp_sock = socket.create_connection((host, port), timeout=10)
                    tcp_sock.setblocking(True)
                except Exception as exc:
                    error_msg = f"ERROR {exc}\n".encode("utf-8")
                    await loop.run_in_executor(
                        None, vsock_conn.sendall, error_msg
                    )
                    logger.error("Tunnel: failed to connect to %s:%d: %s", host, port, exc)
                    return

                # Signal success
                await loop.run_in_executor(None, vsock_conn.sendall, b"OK\n")
                logger.info("Tunnel: connected to %s:%d", host, port)

                # Set longer timeout for data forwarding
                vsock_conn.settimeout(600)  # 10 min for LLM calls
                tcp_sock.settimeout(600)

                # Bidirectional forwarding
                forwarded = await self._forward_bidirectional(
                    loop, vsock_conn, tcp_sock
                )
                self._bytes_forwarded += forwarded
                logger.info(
                    "Tunnel: connection to %s:%d closed (%d bytes forwarded)",
                    host, port, forwarded,
                )

        except Exception:
            logger.exception("Tunnel: error handling connection from CID=%s", addr[0])
        finally:
            vsock_conn.close()
            if tcp_sock is not None:
                tcp_sock.close()

    @staticmethod
    def _read_connect_line(sock: socket.socket) -> str:
        """Read the CONNECT line from the vsock connection.

        Reads byte-by-byte until newline (max 256 bytes).
        """
        buf = b""
        while len(buf) < 256:
            byte = sock.recv(1)
            if not byte:
                raise ConnectionError("Connection closed before CONNECT line")
            if byte == b"\n":
                return buf.decode("utf-8").strip()
            buf += byte
        raise TunnelError("CONNECT line too long (max 256 bytes)")

    @staticmethod
    def _parse_connect(line: str) -> tuple[str, int]:
        """Parse 'CONNECT host:port' into (host, port)."""
        parts = line.split()
        if len(parts) != 2 or parts[0].upper() != "CONNECT":
            raise TunnelError(f"Invalid CONNECT line: {line!r}")

        host_port = parts[1]
        if ":" not in host_port:
            raise TunnelError(f"Missing port in CONNECT target: {host_port!r}")

        host, port_str = host_port.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            raise TunnelError(f"Invalid port in CONNECT target: {port_str!r}")

        if not (1 <= port <= 65535):
            raise TunnelError(f"Port out of range: {port}")

        return host, port

    async def _forward_bidirectional(
        self,
        loop: asyncio.AbstractEventLoop,
        vsock_conn: socket.socket,
        tcp_sock: socket.socket,
    ) -> int:
        """Forward bytes between vsock and TCP until one side closes.

        Returns total bytes forwarded.
        """
        total = 0

        async def forward(src: socket.socket, dst: socket.socket, label: str) -> int:
            """Forward data from src to dst until src closes."""
            forwarded = 0
            try:
                while True:
                    data = await loop.run_in_executor(
                        None, src.recv, TUNNEL_BUFFER_SIZE
                    )
                    if not data:
                        break
                    await loop.run_in_executor(None, dst.sendall, data)
                    forwarded += len(data)
            except (ConnectionError, OSError):
                pass
            return forwarded

        # Run both directions concurrently
        vsock_to_tcp = asyncio.create_task(
            forward(vsock_conn, tcp_sock, "vsock→tcp")
        )
        tcp_to_vsock = asyncio.create_task(
            forward(tcp_sock, vsock_conn, "tcp→vsock")
        )

        # Wait for either direction to finish, then cancel the other
        done, pending = await asyncio.wait(
            {vsock_to_tcp, tcp_to_vsock},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        for task in done:
            try:
                total += task.result()
            except Exception:
                pass

        # Get results from cancelled tasks if they completed before cancellation
        for task in pending:
            if task.done() and not task.cancelled():
                try:
                    total += task.result()
                except Exception:
                    pass

        return total

    async def _cleanup(self) -> None:
        """Close the server socket and cancel outstanding tasks."""
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        for task in list(self._tasks):
            if not task.done():
                task.cancel()
        self._tasks.clear()
