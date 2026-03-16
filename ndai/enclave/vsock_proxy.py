"""Parent-side vsock proxy for Claude API calls from the Nitro Enclave.

Runs on the parent EC2 instance. Listens on AF_VSOCK port 5001 for LLM
call requests from the enclave, forwards them to the Anthropic API over
HTTPS, and returns the serialized response.

The API key is held ONLY on the parent side -- it is never sent into the
enclave.

Protocol (matches vsock_llm_client.py):
    Length-prefixed framing: 4-byte big-endian length header + JSON payload.
    Request:  {"action": "llm_call", "model": ..., "system": ..., ...}
    Response: {"content": [...], "stop_reason": ..., "usage": {...}}
              or {"error": "..."}

Usage:
    proxy = VsockProxy(api_key="sk-ant-...")
    await proxy.run()           # blocks, serving requests
    await proxy.run_background() # returns an asyncio.Task
"""

import asyncio
import json
import logging
import socket
import struct
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# vsock constants
AF_VSOCK = 40
VMADDR_CID_ANY = 0xFFFFFFFF  # 4294967295
LLM_PROXY_PORT = 5001

# Maximum request payload (16 MiB — generous for large tool schemas)
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024


class VsockProxy:
    """Parent-side proxy that forwards enclave LLM requests to Claude API.

    Supports concurrent connections: each enclave request is handled in a
    separate asyncio task so multiple LLM calls can be in flight.
    """

    def __init__(
        self,
        api_key: str,
        port: int = LLM_PROXY_PORT,
        max_concurrent: int = 8,
    ):
        if not api_key:
            raise ValueError("Anthropic API key is required for VsockProxy")
        self.api_key = api_key
        self.port = port
        self.max_concurrent = max_concurrent
        self._client = anthropic.Anthropic(api_key=api_key)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._server_sock: socket.socket | None = None
        self._running = False
        self._tasks: set[asyncio.Task] = set()

    # -- Public interface --------------------------------------------------

    async def run(self) -> None:
        """Start the proxy and serve requests until stopped."""
        self._server_sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((VMADDR_CID_ANY, self.port))
        self._server_sock.listen(self.max_concurrent)
        self._server_sock.setblocking(False)
        self._running = True

        logger.info("VsockProxy listening on vsock port %d (max_concurrent=%d)",
                     self.port, self.max_concurrent)

        loop = asyncio.get_event_loop()
        try:
            while self._running:
                try:
                    conn, addr = await loop.run_in_executor(
                        None, self._accept_with_timeout
                    )
                except TimeoutError:
                    continue

                logger.info("Accepted vsock connection from CID=%s port=%s", *addr)
                task = asyncio.create_task(self._handle_connection(conn, addr))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            await self._cleanup()

    async def run_background(self) -> asyncio.Task:
        """Start the proxy as a background asyncio task.

        Returns the task handle so the caller can cancel it when done.
        """
        task = asyncio.create_task(self.run())
        # Give the event loop a chance to start the server socket
        await asyncio.sleep(0.05)
        return task

    async def stop(self) -> None:
        """Gracefully stop the proxy."""
        logger.info("Stopping VsockProxy")
        self._running = False
        # Wait for in-flight requests to finish (with a timeout)
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=30)
        await self._cleanup()

    # -- Connection handling -----------------------------------------------

    def _accept_with_timeout(self) -> tuple[socket.socket, tuple[int, int]]:
        """Accept a connection with a 1-second timeout.

        Raises TimeoutError if no connection arrives within the timeout,
        allowing the run loop to check self._running.
        """
        assert self._server_sock is not None
        self._server_sock.settimeout(1.0)
        try:
            return self._server_sock.accept()
        except socket.timeout as exc:
            raise TimeoutError from exc

    async def _handle_connection(
        self,
        conn: socket.socket,
        addr: tuple[int, int],
    ) -> None:
        """Handle a single enclave connection: read request, call API, send response."""
        conn.setblocking(True)
        conn.settimeout(300)  # 5 min — LLM calls can be slow
        try:
            async with self._semaphore:
                request = await self._read_frame(conn)
                response = await self._process_request(request)
                await self._write_frame(conn, response)
        except Exception:
            logger.exception("Error handling connection from CID=%s", addr[0])
            # Best-effort error response
            try:
                error_resp = {"error": "Internal proxy error"}
                await self._write_frame(conn, error_resp)
            except Exception:
                pass
        finally:
            conn.close()

    async def _process_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process a single LLM request and return the response dict."""
        action = request.get("action")
        if action != "llm_call":
            return {"error": f"Unknown action: {action}"}

        model = request.get("model", "claude-sonnet-4-20250514")
        system = request.get("system", "")
        messages = request.get("messages", [])
        max_tokens = request.get("max_tokens", 2048)
        tools = request.get("tools")
        tool_choice = request.get("tool_choice")

        logger.info("Proxying LLM call: model=%s, messages=%d, max_tokens=%d",
                     model, len(messages), max_tokens)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        try:
            # Run the synchronous Anthropic SDK call in an executor
            # so we don't block the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self._client.messages.create(**kwargs)
            )
        except anthropic.APIStatusError as exc:
            logger.error("Anthropic API error: %s %s", exc.status_code, exc.message)
            return {"error": f"API error {exc.status_code}: {exc.message}"}
        except anthropic.APIConnectionError as exc:
            logger.error("Anthropic API connection error: %s", exc)
            return {"error": f"API connection error: {exc}"}
        except Exception as exc:
            logger.exception("Unexpected error calling Anthropic API")
            return {"error": f"Unexpected error: {exc}"}

        # Serialize the response to a dict
        return self._serialize_response(response)

    @staticmethod
    def _serialize_response(response: anthropic.types.Message) -> dict[str, Any]:
        """Convert an Anthropic Message into a JSON-serializable dict."""
        content_blocks = []
        for block in response.content:
            if block.type == "text":
                content_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            else:
                # Future-proof: pass through any other block type
                content_blocks.append(block.model_dump())

        return {
            "content": content_blocks,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    # -- Framing -----------------------------------------------------------

    async def _read_frame(self, conn: socket.socket) -> dict[str, Any]:
        """Read a length-prefixed JSON frame from a socket."""
        loop = asyncio.get_event_loop()

        # Read 4-byte length header
        length_bytes = await self._recv_exact_async(loop, conn, 4)
        length = struct.unpack(">I", length_bytes)[0]

        if length > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Payload too large: {length} bytes (max {MAX_PAYLOAD_BYTES})")

        # Read payload
        payload_bytes = await self._recv_exact_async(loop, conn, length)
        return json.loads(payload_bytes.decode("utf-8"))

    async def _write_frame(self, conn: socket.socket, data: dict[str, Any]) -> None:
        """Write a length-prefixed JSON frame to a socket."""
        loop = asyncio.get_event_loop()
        payload = json.dumps(data).encode("utf-8")
        frame = struct.pack(">I", len(payload)) + payload
        await loop.run_in_executor(None, conn.sendall, frame)

    @staticmethod
    async def _recv_exact_async(
        loop: asyncio.AbstractEventLoop,
        sock: socket.socket,
        nbytes: int,
    ) -> bytes:
        """Receive exactly nbytes from a socket, async-wrapped."""
        buf = b""
        while len(buf) < nbytes:
            chunk = await loop.run_in_executor(
                None, sock.recv, min(nbytes - len(buf), 65536)
            )
            if not chunk:
                raise ConnectionError(
                    f"vsock connection closed after {len(buf)}/{nbytes} bytes"
                )
            buf += chunk
        return buf

    # -- Cleanup -----------------------------------------------------------

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
