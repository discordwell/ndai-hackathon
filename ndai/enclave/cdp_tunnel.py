"""Parent-side CDP tunnel: vsock <-> Chrome WebSocket bridge.

Bridges Chrome DevTools Protocol (CDP) traffic between the enclave (over vsock)
and a Chrome instance running on the parent host (over WebSocket/HTTP).

Protocol:
    1. Enclave connects to parent on vsock CDP_PORT
    2. Enclave sends a command line (text, terminated by \\n):
       - "HTTP GET /json/version\\n" → parent proxies HTTP GET to Chrome and
         returns a length-prefixed response frame (4-byte big-endian + body)
       - "CONNECT cdp\\n" → parent discovers Chrome's CDP debugger WebSocket URL,
         opens a WebSocket connection to it, then forwards CDP JSON messages
         bidirectionally using length-prefixed framing over vsock

Frame protocol (for WebSocket mode):
    [4-byte big-endian length][raw CDP JSON message body]

The enclave performs all CDP logic; the parent is a transparent bridge.
"""

import asyncio
import logging
import socket
import struct
from typing import Any

import httpx
import websockets
import websockets.exceptions

logger = logging.getLogger(__name__)

# vsock constants (same as VsockTunnel)
AF_VSOCK = 40
VMADDR_CID_ANY = 0xFFFFFFFF

# Port for CDP tunnel — distinct from command (5000), LLM proxy (5001/5002)
CDP_PORT = 5003

# Buffer size for reads
BUFFER_SIZE = 65536

# Maximum concurrent CDP connections (CDP is typically one debugger session)
MAX_CONCURRENT = 4


class CdpTunnelError(Exception):
    """Error in CDP tunnel operation."""


class CdpTunnel:
    """Parent-side CDP tunnel that bridges enclave vsock to Chrome WebSocket.

    On each connection the enclave sends a command line:
    - "HTTP GET /json/version" → HTTP discovery request forwarded to Chrome
    - "CONNECT cdp"            → bidirectional WebSocket <-> vsock bridge

    Usage:
        tunnel = CdpTunnel()
        await tunnel.run()           # blocks, serving requests
        # or
        task = await tunnel.run_background()  # returns asyncio.Task
    """

    def __init__(
        self,
        port: int = CDP_PORT,
        chrome_ws_url: str = "ws://localhost:9222",
    ):
        self.port = port
        self.chrome_ws_url = chrome_ws_url
        self._server_sock: socket.socket | None = None
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._bytes_forwarded = 0

    # ------------------------------------------------------------------
    # Public lifecycle API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the tunnel and serve connections until stopped."""
        self._server_sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((VMADDR_CID_ANY, self.port))
        self._server_sock.listen(MAX_CONCURRENT)
        self._server_sock.setblocking(False)
        self._running = True

        logger.info(
            "CdpTunnel listening on vsock port %d (chrome: %s)",
            self.port,
            self.chrome_ws_url,
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

                logger.info(
                    "CdpTunnel: accepted connection from CID=%s port=%s", *addr
                )
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
        logger.info(
            "Stopping CdpTunnel (forwarded %d bytes total)", self._bytes_forwarded
        )
        self._running = False
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=30)
        await self._cleanup()

    @property
    def bytes_forwarded(self) -> int:
        """Total bytes forwarded through the tunnel."""
        return self._bytes_forwarded

    # ------------------------------------------------------------------
    # Internal accept helpers
    # ------------------------------------------------------------------

    def _accept_with_timeout(self) -> tuple[socket.socket, tuple[int, int]]:
        """Accept with 1-second timeout for run loop check."""
        assert self._server_sock is not None
        self._server_sock.settimeout(1.0)
        try:
            return self._server_sock.accept()
        except socket.timeout as exc:
            raise TimeoutError from exc

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    async def _handle_connection(
        self,
        vsock_conn: socket.socket,
        addr: tuple[int, int],
    ) -> None:
        """Dispatch an incoming vsock connection based on the command line."""
        vsock_conn.setblocking(True)
        vsock_conn.settimeout(30)

        try:
            loop = asyncio.get_event_loop()
            command_line = await loop.run_in_executor(
                None, self._read_command_line, vsock_conn
            )
            logger.debug("CdpTunnel: command=%r from CID=%s", command_line, addr[0])

            if command_line.upper().startswith("HTTP GET"):
                await self._handle_http(vsock_conn, command_line, loop)
            elif command_line.upper() == "CONNECT CDP":
                await self._handle_cdp_ws(vsock_conn, loop)
            else:
                error = f"ERROR unknown command: {command_line!r}\n".encode()
                await loop.run_in_executor(None, vsock_conn.sendall, error)
                logger.warning(
                    "CdpTunnel: unknown command %r from CID=%s", command_line, addr[0]
                )

        except Exception:
            logger.exception(
                "CdpTunnel: error handling connection from CID=%s", addr[0]
            )
        finally:
            vsock_conn.close()

    # ------------------------------------------------------------------
    # HTTP discovery handler
    # ------------------------------------------------------------------

    async def _handle_http(
        self,
        vsock_conn: socket.socket,
        command_line: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Proxy an HTTP GET to Chrome and send back a length-prefixed response.

        The command line format is: "HTTP GET <path>"
        Response frame: [4-byte big-endian length][response body bytes]
        """
        # Parse path from command: "HTTP GET /json/version"
        parts = command_line.split(None, 2)
        path = parts[2] if len(parts) >= 3 else "/json/version"

        # Derive HTTP URL from chrome_ws_url (ws:// → http://)
        http_base = self.chrome_ws_url.replace("ws://", "http://", 1).replace(
            "wss://", "https://", 1
        )
        # Strip any trailing path from base URL
        if http_base.count("/") > 2:
            http_base = "/".join(http_base.split("/")[:3])
        url = f"{http_base}{path}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                body = resp.content
        except Exception as exc:
            body = f'{{"error": "{exc}"}}'.encode()

        frame = struct.pack(">I", len(body)) + body
        self._bytes_forwarded += len(frame)
        await loop.run_in_executor(None, vsock_conn.sendall, frame)
        logger.debug("CdpTunnel: HTTP response %d bytes for %s", len(body), url)

    # ------------------------------------------------------------------
    # CDP WebSocket bridge handler
    # ------------------------------------------------------------------

    async def _handle_cdp_ws(
        self,
        vsock_conn: socket.socket,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Bridge vsock (length-prefixed frames) ↔ Chrome CDP WebSocket.

        1. Discover the first debuggable target's WebSocket debugger URL via
           Chrome's HTTP /json endpoint.
        2. Connect to that WebSocket.
        3. Forward CDP messages bidirectionally until either side closes.
        """
        # Discover CDP debugger URL
        try:
            ws_debug_url = await self._discover_cdp_url()
        except Exception as exc:
            error = f"ERROR failed to discover CDP URL: {exc}\n".encode()
            await loop.run_in_executor(None, vsock_conn.sendall, error)
            logger.error("CdpTunnel: CDP discovery failed: %s", exc)
            return

        logger.info("CdpTunnel: connecting to Chrome CDP at %s", ws_debug_url)

        try:
            async with websockets.connect(ws_debug_url, max_size=None) as ws:
                # Signal success to enclave
                await loop.run_in_executor(None, vsock_conn.sendall, b"OK\n")
                vsock_conn.settimeout(600)

                forwarded = await self._bridge_frames(loop, vsock_conn, ws)
                self._bytes_forwarded += forwarded
                logger.info(
                    "CdpTunnel: CDP session closed (%d bytes forwarded)", forwarded
                )
        except Exception as exc:
            logger.error("CdpTunnel: WebSocket error: %s", exc)

    async def _discover_cdp_url(self) -> str:
        """Query Chrome's /json endpoint to get a debugger WebSocket URL.

        Returns the webSocketDebuggerUrl of the first available target,
        or falls back to the browser-level debugger URL from /json/version.
        """
        http_base = self.chrome_ws_url.replace("ws://", "http://", 1).replace(
            "wss://", "https://", 1
        )
        if http_base.count("/") > 2:
            http_base = "/".join(http_base.split("/")[:3])

        async with httpx.AsyncClient(timeout=10) as client:
            # Try /json for page targets first
            try:
                resp = await client.get(f"{http_base}/json")
                targets = resp.json()
                for target in targets:
                    url = target.get("webSocketDebuggerUrl")
                    if url:
                        return url
            except Exception:
                pass

            # Fall back to /json/version browser-level debugger
            resp = await client.get(f"{http_base}/json/version")
            info = resp.json()
            url = info.get("webSocketDebuggerUrl")
            if url:
                return url

        raise CdpTunnelError("No webSocketDebuggerUrl found in Chrome /json endpoints")

    # ------------------------------------------------------------------
    # Frame-level bidirectional bridge
    # ------------------------------------------------------------------

    async def _bridge_frames(
        self,
        loop: asyncio.AbstractEventLoop,
        vsock_conn: socket.socket,
        ws: Any,  # websockets.WebSocketClientProtocol
    ) -> int:
        """Bridge length-prefixed frames between vsock and Chrome WebSocket.

        vsock → Chrome: read [4-byte length][body], send body as WS text frame
        Chrome → vsock: receive WS frame, send [4-byte length][body] over vsock

        Returns total bytes forwarded.
        """
        total = 0

        async def vsock_to_ws() -> int:
            """Read framed messages from vsock and send to Chrome WebSocket."""
            forwarded = 0
            try:
                while True:
                    # Read 4-byte length header
                    header = await loop.run_in_executor(
                        None, self._recv_exact, vsock_conn, 4
                    )
                    if not header:
                        break
                    (length,) = struct.unpack(">I", header)
                    if length == 0:
                        break

                    body = await loop.run_in_executor(
                        None, self._recv_exact, vsock_conn, length
                    )
                    if not body:
                        break

                    await ws.send(body.decode("utf-8"))
                    forwarded += 4 + length
            except (ConnectionError, OSError, websockets.exceptions.ConnectionClosed):
                pass
            return forwarded

        async def ws_to_vsock() -> int:
            """Receive messages from Chrome WebSocket and send framed to vsock."""
            forwarded = 0
            try:
                async for message in ws:
                    if isinstance(message, str):
                        body = message.encode("utf-8")
                    else:
                        body = message
                    frame = struct.pack(">I", len(body)) + body
                    await loop.run_in_executor(None, vsock_conn.sendall, frame)
                    forwarded += len(frame)
            except (ConnectionError, OSError, websockets.exceptions.ConnectionClosed):
                pass
            return forwarded

        vsock_to_ws_task = asyncio.create_task(vsock_to_ws())
        ws_to_vsock_task = asyncio.create_task(ws_to_vsock())

        done, pending = await asyncio.wait(
            {vsock_to_ws_task, ws_to_vsock_task},
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

        # Collect bytes from cancelled tasks that completed before cancellation
        for task in pending:
            if task.done() and not task.cancelled():
                try:
                    total += task.result()
                except Exception:
                    pass

        return total

    # ------------------------------------------------------------------
    # Low-level socket helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_command_line(sock: socket.socket) -> str:
        """Read a newline-terminated command line from the vsock connection.

        Reads byte-by-byte until newline (max 512 bytes).
        """
        buf = b""
        while len(buf) < 512:
            byte = sock.recv(1)
            if not byte:
                raise ConnectionError("Connection closed before command line")
            if byte == b"\n":
                return buf.decode("utf-8").strip()
            buf += byte
        raise CdpTunnelError("Command line too long (max 512 bytes)")

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes:
        """Read exactly n bytes from sock, or return b'' on close."""
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return b""
            buf += chunk
        return buf

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

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
