"""Tests for the CDP tunnel (parent-side vsock <-> WebSocket bridge)."""

import pytest
from ndai.enclave.cdp_tunnel import CdpTunnel, CDP_PORT


class TestCdpTunnelInit:
    def test_defaults(self):
        tunnel = CdpTunnel()
        assert tunnel.port == CDP_PORT
        assert tunnel.chrome_ws_url == "ws://localhost:9222"

    def test_custom_config(self):
        tunnel = CdpTunnel(chrome_ws_url="ws://neko:9222", port=5004)
        assert tunnel.port == 5004
        assert tunnel.chrome_ws_url == "ws://neko:9222"

    def test_initial_state(self):
        tunnel = CdpTunnel()
        assert tunnel.bytes_forwarded == 0
        assert not tunnel._running
