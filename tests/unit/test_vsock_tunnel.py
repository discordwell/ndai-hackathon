"""Unit tests for the vsock TCP tunnel."""

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ndai.enclave.vsock_tunnel import (
    ALLOWED_HOSTS,
    TunnelError,
    VsockTunnel,
)


class TestConnectParsing:
    """Test CONNECT line parsing."""

    def test_valid_connect(self):
        """Parse a valid CONNECT line."""
        host, port = VsockTunnel._parse_connect("CONNECT api.openai.com:443")
        assert host == "api.openai.com"
        assert port == 443

    def test_case_insensitive_connect(self):
        """CONNECT keyword should be case-insensitive."""
        host, port = VsockTunnel._parse_connect("connect api.openai.com:443")
        assert host == "api.openai.com"
        assert port == 443

    def test_missing_connect_keyword(self):
        """Missing CONNECT keyword should raise TunnelError."""
        with pytest.raises(TunnelError, match="Invalid CONNECT"):
            VsockTunnel._parse_connect("GET api.openai.com:443")

    def test_missing_port(self):
        """Missing port should raise TunnelError."""
        with pytest.raises(TunnelError, match="Missing port"):
            VsockTunnel._parse_connect("CONNECT api.openai.com")

    def test_invalid_port(self):
        """Non-numeric port should raise TunnelError."""
        with pytest.raises(TunnelError, match="Invalid port"):
            VsockTunnel._parse_connect("CONNECT api.openai.com:abc")

    def test_port_out_of_range(self):
        """Port out of 1-65535 should raise TunnelError."""
        with pytest.raises(TunnelError, match="out of range"):
            VsockTunnel._parse_connect("CONNECT api.openai.com:0")
        with pytest.raises(TunnelError, match="out of range"):
            VsockTunnel._parse_connect("CONNECT api.openai.com:99999")

    def test_empty_line(self):
        """Empty line should raise TunnelError."""
        with pytest.raises(TunnelError, match="Invalid CONNECT"):
            VsockTunnel._parse_connect("")

    def test_ipv6_host(self):
        """IPv6 addresses with colons should parse correctly."""
        # rsplit(":", 1) ensures only the last colon splits off the port
        host, port = VsockTunnel._parse_connect("CONNECT [::1]:443")
        assert host == "[::1]"
        assert port == 443


class TestHostWhitelist:
    def test_default_whitelist(self):
        """Default whitelist should contain OpenAI and Anthropic."""
        assert ("api.openai.com", 443) in ALLOWED_HOSTS
        assert ("api.anthropic.com", 443) in ALLOWED_HOSTS

    def test_custom_whitelist(self):
        """Custom whitelist should override default."""
        custom = {("custom.api.com", 8443)}
        tunnel = VsockTunnel(allowed_hosts=custom)
        assert tunnel.allowed_hosts == custom


class TestReadConnectLine:
    def test_reads_until_newline(self):
        """_read_connect_line reads bytes until newline."""
        sock = MagicMock()
        sock.recv.side_effect = [
            b"C", b"O", b"N", b"N", b"E", b"C", b"T",
            b" ", b"a", b".", b"c", b":", b"4", b"\n",
        ]
        result = VsockTunnel._read_connect_line(sock)
        assert result == "CONNECT a.c:4"

    def test_connection_closed(self):
        """Should raise ConnectionError if socket closes."""
        sock = MagicMock()
        sock.recv.return_value = b""
        with pytest.raises(ConnectionError, match="closed"):
            VsockTunnel._read_connect_line(sock)

    def test_line_too_long(self):
        """Should raise TunnelError for overly long lines."""
        sock = MagicMock()
        sock.recv.return_value = b"X"  # Never sends newline
        with pytest.raises(TunnelError, match="too long"):
            VsockTunnel._read_connect_line(sock)


class TestTunnelLifecycle:
    def test_init_defaults(self):
        """Tunnel should have sensible defaults."""
        tunnel = VsockTunnel()
        assert tunnel.port == 5002
        assert tunnel.max_concurrent == 16
        assert tunnel.bytes_forwarded == 0

    def test_bytes_forwarded_tracking(self):
        """bytes_forwarded property should track total bytes."""
        tunnel = VsockTunnel()
        assert tunnel.bytes_forwarded == 0
        tunnel._bytes_forwarded = 12345
        assert tunnel.bytes_forwarded == 12345


class TestBidirectionalForwarding:
    @pytest.mark.asyncio
    async def test_forward_counts_bytes(self):
        """Bidirectional forwarding should count bytes between two socket pairs.

        We create two pairs of connected sockets (A↔B and C↔D) and use
        the tunnel to forward B↔C. Then write on A and read on D.
        """
        tunnel = VsockTunnel()
        loop = asyncio.get_event_loop()

        # Pair 1: A <-> B
        srv1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv1.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv1.bind(("127.0.0.1", 0))
        srv1.listen(1)
        port1 = srv1.getsockname()[1]

        sock_a = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_a.connect(("127.0.0.1", port1))
        sock_b, _ = srv1.accept()

        # Pair 2: C <-> D
        srv2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv2.bind(("127.0.0.1", 0))
        srv2.listen(1)
        port2 = srv2.getsockname()[1]

        sock_c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_c.connect(("127.0.0.1", port2))
        sock_d, _ = srv2.accept()

        for s in [sock_a, sock_b, sock_c, sock_d]:
            s.settimeout(3)

        # Forward B <-> C in the background
        forward_task = asyncio.create_task(
            tunnel._forward_bidirectional(loop, sock_b, sock_c)
        )

        # Write on A, data goes A→B→(forward)→C→D
        test_data = b"Hello through tunnel!"
        await loop.run_in_executor(None, sock_a.sendall, test_data)
        await loop.run_in_executor(None, sock_a.shutdown, socket.SHUT_WR)

        # Read on D
        received = await loop.run_in_executor(None, sock_d.recv, 4096)
        assert received == test_data

        # Close sockets to let forwarding finish
        sock_d.shutdown(socket.SHUT_WR)
        await asyncio.sleep(0.1)
        sock_a.close()
        sock_d.close()

        forwarded = await asyncio.wait_for(forward_task, timeout=5)
        assert forwarded >= len(test_data)

        sock_b.close()
        sock_c.close()
        srv1.close()
        srv2.close()
