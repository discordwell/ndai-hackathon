"""Unit tests for the tunnel LLM client."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from ndai.enclave.tunnel_llm_client import (
    TunnelConnection,
    TunnelError,
    TunnelTransport,
    TunnelOpenAILLMClient,
)


class TestTunnelConnection:
    """Test the TunnelConnection CONNECT handshake."""

    def test_read_line(self):
        """_read_line reads bytes until newline."""
        sock = MagicMock()
        sock.recv.side_effect = [b"O", b"K", b"\n"]
        result = TunnelConnection._read_line(sock)
        assert result == "OK"

    def test_read_line_closed(self):
        """Connection closed during handshake raises TunnelError."""
        sock = MagicMock()
        sock.recv.return_value = b""
        with pytest.raises(TunnelError, match="closed"):
            TunnelConnection._read_line(sock)

    def test_read_line_too_long(self):
        """Overly long response raises TunnelError."""
        sock = MagicMock()
        sock.recv.return_value = b"X"
        with pytest.raises(TunnelError, match="too long"):
            TunnelConnection._read_line(sock)


class TestTunnelTransport:
    """Test the httpx transport layer."""

    def test_parse_response_basic(self):
        """Basic HTTP response parsing."""
        transport = TunnelTransport()
        raw = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"ok\":true}"
        response = transport._parse_response(raw)
        assert response.status_code == 200
        assert response.content == b'{"ok":true}'

    def test_parse_response_no_body(self):
        """Response with empty body."""
        transport = TunnelTransport()
        raw = b"HTTP/1.1 204 No Content\r\n\r\n"
        response = transport._parse_response(raw)
        assert response.status_code == 204
        assert response.content == b""

    def test_parse_response_404(self):
        """Error response parsing."""
        transport = TunnelTransport()
        raw = b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\n\r\nNot Found"
        response = transport._parse_response(raw)
        assert response.status_code == 404
        assert response.content == b"Not Found"

    def test_parse_response_missing_header_terminator(self):
        """Missing \\r\\n\\r\\n should raise TunnelError."""
        transport = TunnelTransport()
        with pytest.raises(TunnelError, match="no header terminator"):
            transport._parse_response(b"HTTP/1.1 200 OK")

    def test_decode_chunked(self):
        """Chunked transfer encoding decoding."""
        transport = TunnelTransport()
        chunked = b"5\r\nHello\r\n6\r\n World\r\n0\r\n\r\n"
        result = transport._decode_chunked(chunked)
        assert result == b"Hello World"

    def test_decode_chunked_empty(self):
        """Empty chunked body."""
        transport = TunnelTransport()
        chunked = b"0\r\n\r\n"
        result = transport._decode_chunked(chunked)
        assert result == b""

    def test_decode_chunked_with_extensions(self):
        """Chunked encoding with chunk extensions."""
        transport = TunnelTransport()
        chunked = b"5;ext=val\r\nHello\r\n0\r\n\r\n"
        result = transport._decode_chunked(chunked)
        assert result == b"Hello"


class TestTunnelOpenAILLMClient:
    """Test the TunnelOpenAILLMClient wrapper."""

    def test_delegates_to_inner_client(self):
        """Methods should delegate to the inner OpenAILLMClient."""
        with patch("ndai.enclave.tunnel_llm_client.create_openai_client") as mock_create:
            mock_openai = MagicMock()
            mock_create.return_value = mock_openai

            client = TunnelOpenAILLMClient(
                api_key="sk-test",
                model="gpt-4o",
                parent_cid=3,
                tunnel_port=5002,
            )

            # The inner client should have been created
            mock_create.assert_called_once_with(
                api_key="sk-test",
                model="gpt-4o",
                parent_cid=3,
                tunnel_port=5002,
            )

    def test_has_expected_methods(self):
        """Should expose create_message, extract_tool_use, extract_text."""
        with patch("ndai.enclave.tunnel_llm_client.create_openai_client"):
            client = TunnelOpenAILLMClient(api_key="sk-test")
            assert hasattr(client, "create_message")
            assert hasattr(client, "extract_tool_use")
            assert hasattr(client, "extract_text")
            assert hasattr(client, "_clean_messages")
