"""Enclave-side CDP client that connects through the parent's CdpTunnel.

In Nitro mode the enclave has NO network — only vsock. This client connects
to the parent's CdpTunnel on vsock port 5003, which bridges to Chrome.

In simulated mode it connects directly via TCP WebSocket to Chrome's
remote-debugging endpoint (ws://localhost:9222 by default).

Protocol (Nitro mode):
    1. Open vsock connection to parent CID 3 port 5003
    2. Send "HTTP GET /json/version\\n" → receive length-prefixed JSON response
    3. Parse webSocketDebuggerUrl from the JSON
    4. Open a second vsock connection to parent CID 3 port 5003
    5. Send "CONNECT cdp\\n" → receive "OK\\n"
    6. Exchange CDP JSON messages using length-prefixed framing

Protocol (Simulated mode):
    1. httpx GET http://localhost:9222/json/version to discover debugger URL
    2. websockets.connect() directly to debugger URL

Frame protocol (Nitro WebSocket mode):
    [4-byte big-endian length][raw CDP JSON message body]
"""

import asyncio
import itertools
import json
import logging
import socket
import struct
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# vsock address family constant (Linux kernel)
AF_VSOCK = 40

# Parent VM CID (the host side in Nitro terminology)
PARENT_CID = 3

# vsock port where the parent's CdpTunnel listens
CDP_PORT = 5003

# Command ID counter — shared across all TunnelCdpClient instances to keep IDs unique
_id_counter = itertools.count(1)


class TunnelCdpError(Exception):
    """Error in the enclave-side CDP client."""


class TunnelCdpClient:
    """Lightweight CDP client for the enclave.

    Uses the ``websockets`` library (not Playwright — too heavy for an enclave).

    In simulated mode the client connects directly to Chrome's WebSocket
    debugger.  In Nitro mode all traffic is routed through the parent's
    CdpTunnel over vsock.

    Usage::

        client = TunnelCdpClient(simulated=True)
        await client.connect()
        result = await client.send_command("Page.navigate", {"url": "https://example.com"})
        await client.close()
    """

    def __init__(
        self,
        simulated: bool = True,
        chrome_url: str = "ws://localhost:9222",
        vsock_port: int = CDP_PORT,
        parent_cid: int = PARENT_CID,
    ) -> None:
        self.simulated = simulated
        self.chrome_url = chrome_url
        self.vsock_port = vsock_port
        self.parent_cid = parent_cid

        # Set after connect()
        self._ws: Any = None  # websockets connection (simulated) or None (Nitro)
        self._vsock: socket.socket | None = None  # raw vsock (Nitro mode)
        self._recv_task: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._closed = False

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_command(method: str, params: dict) -> dict:
        """Build a CDP command dict with an auto-incrementing id."""
        return {
            "id": next(_id_counter),
            "method": method,
            "params": params,
        }

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish a CDP session.

        Simulated: HTTP discovery + direct WebSocket connect.
        Nitro: vsock HTTP discovery + vsock CONNECT cdp.
        """
        if self.simulated:
            await self._connect_simulated()
        else:
            await self._connect_nitro()

        # Start background receive loop
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def _connect_simulated(self) -> None:
        """Connect directly to Chrome's WebSocket debugger via TCP."""
        import websockets  # type: ignore

        # Derive HTTP base URL (ws:// → http://)
        http_base = self.chrome_url.replace("ws://", "http://").replace("wss://", "https://")
        # Strip any trailing path to get just the host:port
        if http_base.count("/") > 2:
            http_base = "/".join(http_base.split("/")[:3])

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{http_base}/json/version")
            info = resp.json()

        debugger_url = info.get("webSocketDebuggerUrl")
        if not debugger_url:
            raise TunnelCdpError(
                f"No webSocketDebuggerUrl in Chrome /json/version response: {info}"
            )

        logger.debug("TunnelCdpClient (simulated): connecting to %s", debugger_url)
        self._ws = await websockets.connect(debugger_url, max_size=None)
        logger.info("TunnelCdpClient (simulated): connected to Chrome CDP")

    async def _connect_nitro(self) -> None:
        """Connect through the parent's CdpTunnel over vsock (Nitro mode).

        Step 1: Open a vsock connection, send "HTTP GET /json/version\\n",
                read the length-prefixed response, parse debugger URL.

        Step 2: Open a second vsock connection, send "CONNECT cdp\\n",
                read "OK\\n" acknowledgement.  This connection is kept open
                for CDP message exchange.
        """
        loop = asyncio.get_event_loop()

        # --- Step 1: HTTP discovery ---
        vsock_http = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        vsock_http.settimeout(30)
        try:
            await loop.run_in_executor(
                None, vsock_http.connect, (self.parent_cid, self.vsock_port)
            )
            await loop.run_in_executor(
                None, vsock_http.sendall, b"HTTP GET /json/version\n"
            )

            # Read 4-byte length header
            header = await loop.run_in_executor(
                None, self._recv_exact, vsock_http, 4
            )
            if len(header) < 4:
                raise TunnelCdpError("Truncated length header from parent CdpTunnel")
            (length,) = struct.unpack(">I", header)

            # Read response body
            body = await loop.run_in_executor(
                None, self._recv_exact, vsock_http, length
            )
        finally:
            vsock_http.close()

        info = json.loads(body.decode("utf-8"))
        if "error" in info:
            raise TunnelCdpError(f"CdpTunnel HTTP error: {info['error']}")

        logger.debug("TunnelCdpClient (Nitro): Chrome version info: %s", info)

        # --- Step 2: CONNECT cdp ---
        vsock_cdp = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        vsock_cdp.settimeout(30)
        try:
            await loop.run_in_executor(
                None, vsock_cdp.connect, (self.parent_cid, self.vsock_port)
            )
            await loop.run_in_executor(
                None, vsock_cdp.sendall, b"CONNECT cdp\n"
            )

            # Read "OK\n" acknowledgement
            ok_line = await loop.run_in_executor(
                None, self._read_line, vsock_cdp
            )
        except Exception:
            vsock_cdp.close()
            raise

        if not ok_line.upper().startswith("OK"):
            vsock_cdp.close()
            raise TunnelCdpError(f"CONNECT cdp rejected by parent: {ok_line!r}")

        vsock_cdp.settimeout(600)  # Long timeout for CDP session
        self._vsock = vsock_cdp
        logger.info("TunnelCdpClient (Nitro): CDP session established via vsock")

    # ------------------------------------------------------------------
    # Send / receive
    # ------------------------------------------------------------------

    async def send_command(self, method: str, params: dict | None = None) -> dict:
        """Send a CDP command and wait for the matching response.

        Args:
            method: CDP method name, e.g. "Page.navigate".
            params: CDP method parameters (defaults to empty dict).

        Returns:
            The ``result`` field of the CDP response dict.

        Raises:
            TunnelCdpError: If the CDP response contains an ``error`` field
                or if the connection is closed.
        """
        if self._closed:
            raise TunnelCdpError("TunnelCdpClient is closed")

        cmd = self._build_command(method, params or {})
        cmd_id: int = cmd["id"]
        payload = json.dumps(cmd).encode("utf-8")

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[cmd_id] = fut

        try:
            if self.simulated:
                # websockets transport
                await self._ws.send(payload.decode("utf-8"))
            else:
                # Nitro: length-prefixed frame over vsock
                frame = struct.pack(">I", len(payload)) + payload
                assert self._vsock is not None
                await loop.run_in_executor(None, self._vsock.sendall, frame)
        except Exception as exc:
            self._pending.pop(cmd_id, None)
            fut.cancel()
            raise TunnelCdpError(f"Failed to send CDP command: {exc}") from exc

        response = await fut
        if "error" in response:
            raise TunnelCdpError(
                f"CDP error for {method}: {response['error']}"
            )
        return response.get("result", {})

    # ------------------------------------------------------------------
    # Background receive loop
    # ------------------------------------------------------------------

    async def _recv_loop(self) -> None:
        """Receive CDP messages and dispatch to waiting futures.

        Runs as a background asyncio task for the lifetime of the connection.
        """
        try:
            if self.simulated:
                await self._recv_loop_ws()
            else:
                await self._recv_loop_vsock()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("TunnelCdpClient recv loop exited: %s", exc)
        finally:
            # Cancel all pending futures on disconnect
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(TunnelCdpError("CDP connection closed"))
            self._pending.clear()

    async def _recv_loop_ws(self) -> None:
        """Receive loop for simulated (direct WebSocket) mode."""
        import websockets.exceptions  # type: ignore

        try:
            async for raw in self._ws:
                self._dispatch(raw if isinstance(raw, str) else raw.decode("utf-8"))
        except websockets.exceptions.ConnectionClosed:
            pass

    async def _recv_loop_vsock(self) -> None:
        """Receive loop for Nitro (vsock length-framed) mode."""
        loop = asyncio.get_event_loop()
        assert self._vsock is not None

        while not self._closed:
            # Read 4-byte length header
            try:
                header = await loop.run_in_executor(
                    None, self._recv_exact, self._vsock, 4
                )
            except OSError:
                break

            if len(header) < 4:
                break  # Connection closed

            (length,) = struct.unpack(">I", header)
            if length == 0:
                break

            try:
                body = await loop.run_in_executor(
                    None, self._recv_exact, self._vsock, length
                )
            except OSError:
                break

            if len(body) < length:
                break  # Truncated read — connection closed

            self._dispatch(body.decode("utf-8"))

    def _dispatch(self, raw: str) -> None:
        """Parse a CDP message and resolve the matching pending future."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("TunnelCdpClient: invalid JSON from CDP: %r", raw[:200])
            return

        msg_id = msg.get("id")
        if msg_id is not None and msg_id in self._pending:
            fut = self._pending.pop(msg_id)
            if not fut.done():
                fut.set_result(msg)
        else:
            # Unsolicited event — log at debug level
            logger.debug(
                "TunnelCdpClient: unhandled CDP event method=%s",
                msg.get("method", "<no method>"),
            )

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Cleanly close the CDP session."""
        self._closed = True

        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
            self._recv_task = None

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._vsock is not None:
            try:
                self._vsock.close()
            except Exception:
                pass
            self._vsock = None

        logger.info("TunnelCdpClient: closed")

    # ------------------------------------------------------------------
    # Low-level socket helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes:
        """Read exactly n bytes from sock, or return partial bytes on close."""
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return buf  # Connection closed — return what we have
            buf += chunk
        return buf

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        """Read a newline-terminated line from sock (max 512 bytes)."""
        buf = b""
        while len(buf) < 512:
            byte = sock.recv(1)
            if not byte:
                raise TunnelCdpError("Connection closed during handshake")
            if byte == b"\n":
                return buf.decode("utf-8").strip()
            buf += byte
        raise TunnelCdpError("Response line too long (max 512 bytes)")
