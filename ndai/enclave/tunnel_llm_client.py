"""Enclave-side LLM client that routes through the vsock TCP tunnel.

Instead of sending plaintext JSON through the vsock proxy (where the parent
can read everything), this client establishes a TLS connection through the
tunnel. The parent only sees encrypted ciphertext.

Flow:
    1. Connect to parent's tunnel on vsock TUNNEL_PORT
    2. Send "CONNECT api.openai.com:443\n"
    3. Receive "OK\n"
    4. Perform TLS handshake through the tunnel (parent sees ciphertext only)
    5. Send HTTPS requests to the LLM API
    6. Close connection

This module provides:
- TunnelTransport: httpx.BaseTransport that routes through the vsock tunnel
- TunnelOpenAILLMClient: OpenAI client using the tunnel transport
"""

import logging
import socket
import ssl
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# vsock constants
AF_VSOCK = 40
VMADDR_CID_HOST = 3
TUNNEL_PORT = 5002


class TunnelError(Exception):
    """Error establishing or using the tunnel."""


class TunnelConnection:
    """A single tunnel connection through vsock to a remote host.

    Handles the CONNECT handshake and TLS upgrade.
    """

    def __init__(
        self,
        host: str,
        port: int,
        parent_cid: int = VMADDR_CID_HOST,
        tunnel_port: int = TUNNEL_PORT,
    ):
        self.host = host
        self.port = port
        self.parent_cid = parent_cid
        self.tunnel_port = tunnel_port
        self._sock: socket.socket | None = None
        self._ssl_sock: ssl.SSLSocket | None = None

    def connect(self) -> ssl.SSLSocket:
        """Establish tunnel connection and perform TLS handshake.

        Returns an SSL socket ready for HTTPS communication.
        """
        # Step 1: Connect to tunnel via vsock
        vsock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        vsock.settimeout(30)
        try:
            vsock.connect((self.parent_cid, self.tunnel_port))
        except OSError as exc:
            vsock.close()
            raise TunnelError(f"Failed to connect to tunnel: {exc}") from exc

        # Step 2: Send CONNECT request
        connect_line = f"CONNECT {self.host}:{self.port}\n".encode("utf-8")
        try:
            vsock.sendall(connect_line)
        except OSError as exc:
            vsock.close()
            raise TunnelError(f"Failed to send CONNECT: {exc}") from exc

        # Step 3: Read response
        response = self._read_line(vsock)
        if response != "OK":
            vsock.close()
            raise TunnelError(f"Tunnel CONNECT failed: {response}")

        self._sock = vsock

        # Step 4: TLS handshake through the tunnel
        ssl_context = ssl.create_default_context()
        try:
            self._ssl_sock = ssl_context.wrap_socket(
                vsock, server_hostname=self.host
            )
        except ssl.SSLError as exc:
            vsock.close()
            raise TunnelError(f"TLS handshake failed: {exc}") from exc

        # Set longer timeout for data transfer
        self._ssl_sock.settimeout(300)  # 5 min for LLM calls
        logger.debug("Tunnel TLS connection established to %s:%d", self.host, self.port)
        return self._ssl_sock

    def close(self) -> None:
        """Close the tunnel connection."""
        if self._ssl_sock:
            try:
                self._ssl_sock.close()
            except Exception:
                pass
            self._ssl_sock = None
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        """Read a line from the socket (up to newline, max 256 bytes)."""
        buf = b""
        while len(buf) < 256:
            byte = sock.recv(1)
            if not byte:
                raise TunnelError("Connection closed during handshake")
            if byte == b"\n":
                return buf.decode("utf-8").strip()
            buf += byte
        raise TunnelError("Response line too long")


class TunnelTransport(httpx.BaseTransport):
    """httpx transport that routes requests through the vsock TCP tunnel.

    Each request creates a new tunnel connection (per-request, matching
    the 3-5 LLM calls per negotiation pattern).

    Usage:
        transport = TunnelTransport()
        client = httpx.Client(transport=transport)
        # Now any request to api.openai.com goes through the tunnel
    """

    def __init__(
        self,
        parent_cid: int = VMADDR_CID_HOST,
        tunnel_port: int = TUNNEL_PORT,
    ):
        self._parent_cid = parent_cid
        self._tunnel_port = tunnel_port

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Route an HTTP request through the vsock tunnel."""
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)

        tunnel = TunnelConnection(
            host=host,
            port=port,
            parent_cid=self._parent_cid,
            tunnel_port=self._tunnel_port,
        )

        try:
            ssl_sock = tunnel.connect()

            # Build raw HTTP request
            path = request.url.raw_path.decode("ascii") if isinstance(request.url.raw_path, bytes) else str(request.url.raw_path)
            headers = request.headers
            body = request.content

            # Send HTTP request over TLS
            request_line = f"{request.method} {path} HTTP/1.1\r\n"
            ssl_sock.sendall(request_line.encode("ascii"))

            # Send headers
            for name, value in headers.items():
                header_line = f"{name}: {value}\r\n"
                ssl_sock.sendall(header_line.encode("ascii"))

            # Ensure Host header
            if "host" not in {h.lower() for h in headers}:
                ssl_sock.sendall(f"Host: {host}\r\n".encode("ascii"))

            # Ensure Connection: close for simplicity
            ssl_sock.sendall(b"Connection: close\r\n")
            ssl_sock.sendall(b"\r\n")

            # Send body
            if body:
                ssl_sock.sendall(body)

            # Read response
            response_data = b""
            while True:
                chunk = ssl_sock.recv(65536)
                if not chunk:
                    break
                response_data += chunk

            # Parse HTTP response
            return self._parse_response(response_data)

        finally:
            tunnel.close()

    def _parse_response(self, raw: bytes) -> httpx.Response:
        """Parse raw HTTP response bytes into an httpx.Response."""
        # Split headers and body
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            raise TunnelError("Invalid HTTP response: no header terminator")

        header_section = raw[:header_end].decode("ascii", errors="replace")
        body = raw[header_end + 4:]

        lines = header_section.split("\r\n")
        if not lines:
            raise TunnelError("Empty HTTP response")

        # Parse status line: "HTTP/1.1 200 OK"
        status_parts = lines[0].split(" ", 2)
        if len(status_parts) < 2:
            raise TunnelError(f"Invalid status line: {lines[0]!r}")

        status_code = int(status_parts[1])

        # Parse headers
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip()] = value.strip()

        # Handle chunked transfer encoding
        if headers.get("Transfer-Encoding", "").lower() == "chunked":
            body = self._decode_chunked(body)

        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=body,
        )

    @staticmethod
    def _decode_chunked(data: bytes) -> bytes:
        """Decode chunked transfer encoding."""
        result = b""
        pos = 0
        while pos < len(data):
            # Find chunk size line
            line_end = data.find(b"\r\n", pos)
            if line_end == -1:
                break
            size_str = data[pos:line_end].decode("ascii").strip()
            if not size_str:
                break
            # Handle chunk extensions (;ext=value)
            if ";" in size_str:
                size_str = size_str.split(";")[0]
            chunk_size = int(size_str, 16)
            if chunk_size == 0:
                break
            chunk_start = line_end + 2
            chunk_end = chunk_start + chunk_size
            result += data[chunk_start:chunk_end]
            pos = chunk_end + 2  # Skip trailing \r\n
        return result


def create_openai_client(
    api_key: str,
    model: str = "gpt-4o",
    parent_cid: int = VMADDR_CID_HOST,
    tunnel_port: int = TUNNEL_PORT,
) -> "openai.OpenAI":
    """Create an OpenAI client that routes through the vsock tunnel.

    The client performs TLS directly from the enclave; the parent
    only sees encrypted bytes.

    Args:
        api_key: OpenAI API key (decrypted inside enclave).
        model: Model name (not used here, but for caller reference).
        parent_cid: Parent vsock CID.
        tunnel_port: Tunnel vsock port.

    Returns:
        openai.OpenAI client configured with tunnel transport.
    """
    import openai

    transport = TunnelTransport(parent_cid=parent_cid, tunnel_port=tunnel_port)
    http_client = httpx.Client(transport=transport)
    return openai.OpenAI(api_key=api_key, http_client=http_client)


class TunnelOpenAILLMClient:
    """OpenAI LLM client that routes through the vsock TCP tunnel.

    Drop-in replacement for OpenAILLMClient that ensures all API traffic
    is encrypted end-to-end (enclave ↔ OpenAI), invisible to the parent.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        parent_cid: int = VMADDR_CID_HOST,
        tunnel_port: int = TUNNEL_PORT,
    ):
        from ndai.enclave.agents.openai_llm_client import OpenAILLMClient

        # Create OpenAI client with tunnel transport
        client = create_openai_client(
            api_key=api_key,
            model=model,
            parent_cid=parent_cid,
            tunnel_port=tunnel_port,
        )
        # Wrap in OpenAILLMClient, injecting the tunneled client
        self._inner = OpenAILLMClient(api_key=api_key, model=model)
        self._inner.client = client

    def create_message(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.create_message(*args, **kwargs)

    def extract_tool_use(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.extract_tool_use(*args, **kwargs)

    def extract_text(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.extract_text(*args, **kwargs)

    @staticmethod
    def _clean_messages(*args: Any, **kwargs: Any) -> Any:
        from ndai.enclave.agents.openai_llm_client import OpenAILLMClient
        return OpenAILLMClient._clean_messages(*args, **kwargs)
