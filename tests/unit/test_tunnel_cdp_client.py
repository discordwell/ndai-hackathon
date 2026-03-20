"""Tests for the enclave-side CDP client."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ndai.enclave.tunnel_cdp_client import TunnelCdpClient


class TestTunnelCdpClientInit:
    def test_simulated_mode(self):
        client = TunnelCdpClient(simulated=True, chrome_url="ws://localhost:9222")
        assert client.simulated is True

    def test_nitro_mode(self):
        client = TunnelCdpClient(simulated=False)
        assert client.simulated is False

    def test_default_vsock_port(self):
        from ndai.enclave.tunnel_cdp_client import CDP_PORT
        client = TunnelCdpClient(simulated=False)
        assert client.vsock_port == CDP_PORT

    def test_default_parent_cid(self):
        from ndai.enclave.tunnel_cdp_client import PARENT_CID
        client = TunnelCdpClient(simulated=False)
        assert client.parent_cid == PARENT_CID

    def test_custom_chrome_url(self):
        client = TunnelCdpClient(simulated=True, chrome_url="ws://neko:9222")
        assert client.chrome_url == "ws://neko:9222"

    def test_initial_state(self):
        client = TunnelCdpClient(simulated=True)
        assert client._ws is None
        assert client._vsock is None
        assert client._recv_task is None
        assert client._pending == {}
        assert client._closed is False


class TestCdpCommandBuilding:
    def test_navigate_command(self):
        cmd = TunnelCdpClient._build_command("Page.navigate", {"url": "https://example.com"})
        assert cmd["method"] == "Page.navigate"
        assert cmd["params"]["url"] == "https://example.com"
        assert "id" in cmd

    def test_screenshot_command(self):
        cmd = TunnelCdpClient._build_command("Page.captureScreenshot", {})
        assert cmd["method"] == "Page.captureScreenshot"

    def test_command_id_is_int(self):
        cmd = TunnelCdpClient._build_command("Runtime.evaluate", {"expression": "1+1"})
        assert isinstance(cmd["id"], int)

    def test_command_ids_are_unique(self):
        cmd1 = TunnelCdpClient._build_command("Page.navigate", {"url": "https://a.com"})
        cmd2 = TunnelCdpClient._build_command("Page.navigate", {"url": "https://b.com"})
        assert cmd1["id"] != cmd2["id"]

    def test_command_ids_increment(self):
        cmd1 = TunnelCdpClient._build_command("A.method", {})
        cmd2 = TunnelCdpClient._build_command("B.method", {})
        assert cmd2["id"] == cmd1["id"] + 1

    def test_empty_params(self):
        cmd = TunnelCdpClient._build_command("Page.reload", {})
        assert cmd["params"] == {}

    def test_complex_params(self):
        params = {"format": "jpeg", "quality": 80, "captureBeyondViewport": True}
        cmd = TunnelCdpClient._build_command("Page.captureScreenshot", params)
        assert cmd["params"] == params


class TestDispatch:
    """Test internal message dispatch logic."""

    def test_dispatch_resolves_pending_future(self):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            client = TunnelCdpClient(simulated=True)
            fut = loop.create_future()
            client._pending[42] = fut

            response = json.dumps({"id": 42, "result": {"frameId": "abc"}})
            client._dispatch(response)

            assert fut.done()
            assert fut.result() == {"id": 42, "result": {"frameId": "abc"}}
            assert 42 not in client._pending
        finally:
            loop.close()

    def test_dispatch_ignores_unknown_id(self):
        client = TunnelCdpClient(simulated=True)
        # Should not raise even with no pending futures
        client._dispatch(json.dumps({"id": 999, "result": {}}))

    def test_dispatch_handles_events(self):
        """CDP events (no id field) should not raise."""
        client = TunnelCdpClient(simulated=True)
        event = json.dumps({"method": "Page.loadEventFired", "params": {"timestamp": 1.0}})
        client._dispatch(event)  # Must not raise

    def test_dispatch_handles_invalid_json(self):
        """Invalid JSON should be silently ignored."""
        client = TunnelCdpClient(simulated=True)
        client._dispatch("not-valid-json{{{")  # Must not raise


class TestRecvExact:
    """Test the low-level socket helper."""

    def test_recv_exact_full_read(self):
        import socket
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [b"hel", b"lo"]
        result = TunnelCdpClient._recv_exact(sock, 5)
        assert result == b"hello"

    def test_recv_exact_connection_closed(self):
        import socket
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = b""
        result = TunnelCdpClient._recv_exact(sock, 4)
        assert result == b""

    def test_recv_exact_single_chunk(self):
        import socket
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = b"abcd"
        result = TunnelCdpClient._recv_exact(sock, 4)
        assert result == b"abcd"


class TestReadLine:
    """Test the newline-terminated line reader."""

    def test_read_line_ok(self):
        import socket
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [b"O", b"K", b"\n"]
        result = TunnelCdpClient._read_line(sock)
        assert result == "OK"

    def test_read_line_strips_whitespace(self):
        import socket
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [b"O", b"K", b" ", b"\n"]
        result = TunnelCdpClient._read_line(sock)
        assert result == "OK"

    def test_read_line_closed(self):
        from ndai.enclave.tunnel_cdp_client import TunnelCdpError
        import socket
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = b""
        with pytest.raises(TunnelCdpError, match="closed"):
            TunnelCdpClient._read_line(sock)


class TestSendCommandClosed:
    """Test that send_command raises when the client is closed."""

    @pytest.mark.asyncio
    async def test_send_command_when_closed(self):
        from ndai.enclave.tunnel_cdp_client import TunnelCdpError
        client = TunnelCdpClient(simulated=True)
        client._closed = True
        with pytest.raises(TunnelCdpError, match="closed"):
            await client.send_command("Page.navigate", {"url": "https://example.com"})


class TestConnectSimulated:
    """Test the simulated connect path (mocked httpx + websockets)."""

    @pytest.mark.asyncio
    async def test_connect_simulated_happy_path(self):
        """_connect_simulated should fetch /json/version and call websockets.connect."""
        debugger_url = "ws://localhost:9222/devtools/page/abc"
        version_info = {"webSocketDebuggerUrl": debugger_url, "Browser": "Chrome"}

        mock_ws = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = version_info

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch("ndai.enclave.tunnel_cdp_client.httpx.AsyncClient", return_value=mock_http_client):
            import sys
            import types
            # Inject a mock websockets module so the lazy import inside
            # _connect_simulated picks it up.
            fake_ws_module = types.ModuleType("websockets")
            fake_ws_module.connect = AsyncMock(return_value=mock_ws)
            original = sys.modules.get("websockets")
            sys.modules["websockets"] = fake_ws_module
            try:
                client = TunnelCdpClient(simulated=True, chrome_url="ws://localhost:9222")
                await client._connect_simulated()
                assert client._ws is mock_ws
                fake_ws_module.connect.assert_called_once_with(debugger_url, max_size=None)
            finally:
                if original is None:
                    sys.modules.pop("websockets", None)
                else:
                    sys.modules["websockets"] = original

    @pytest.mark.asyncio
    async def test_connect_simulated_no_debugger_url(self):
        """Should raise TunnelCdpError when webSocketDebuggerUrl is missing."""
        from ndai.enclave.tunnel_cdp_client import TunnelCdpError

        version_info = {"Browser": "Chrome"}  # No webSocketDebuggerUrl

        mock_response = MagicMock()
        mock_response.json.return_value = version_info

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        with patch("ndai.enclave.tunnel_cdp_client.httpx.AsyncClient", return_value=mock_http_client):
            client = TunnelCdpClient(simulated=True, chrome_url="ws://localhost:9222")
            with pytest.raises(TunnelCdpError, match="webSocketDebuggerUrl"):
                await client._connect_simulated()
