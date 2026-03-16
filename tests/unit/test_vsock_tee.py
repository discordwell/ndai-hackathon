"""Tests for the TEE vsock integration layer.

Tests cover:
1. VsockLLMClient — serialization, response parsing, error handling
2. VsockProxy — request processing, response serialization
3. Enclave app — request parsing, dispatch, result serialization
4. EnclaveNegotiationSession — wiring with VsockLLMClient

These tests run without actual AF_VSOCK sockets by mocking at the
socket/transport level.
"""

import asyncio
import json
import socket
import struct
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    NegotiationResult,
    SecurityParams,
)
from ndai.enclave.session import SessionConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _frame(data: dict) -> bytes:
    """Create a length-prefixed frame from a dict."""
    payload = json.dumps(data).encode("utf-8")
    return struct.pack(">I", len(payload)) + payload


def _make_invention(**overrides) -> InventionSubmission:
    defaults = {
        "title": "Test Invention",
        "full_description": "A novel approach to testing.",
        "technical_domain": "software",
        "novelty_claims": ["Novel test approach"],
        "prior_art_known": ["Existing tests"],
        "potential_applications": ["Better testing"],
        "development_stage": "prototype",
        "self_assessed_value": 0.75,
        "outside_option_value": 0.3,
        "confidential_sections": ["Secret sauce"],
        "max_disclosure_fraction": 0.8,
    }
    defaults.update(overrides)
    return InventionSubmission(**defaults)


def _make_negotiation_request(**overrides) -> dict:
    defaults = {
        "action": "negotiate",
        "invention": {
            "title": "Test Invention",
            "full_description": "A novel approach to testing.",
            "technical_domain": "software",
            "novelty_claims": ["Novel test approach"],
            "prior_art_known": ["Existing tests"],
            "potential_applications": ["Better testing"],
            "development_stage": "prototype",
            "self_assessed_value": 0.75,
            "outside_option_value": 0.3,
            "confidential_sections": ["Secret sauce"],
            "max_disclosure_fraction": 0.8,
        },
        "budget_cap": 0.5,
        "security_params": {"k": 3, "p": 0.5, "c": 1.0, "gamma": 1.0},
        "max_rounds": 3,
        "anthropic_model": "claude-sonnet-4-20250514",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# VsockLLMClient tests
# ---------------------------------------------------------------------------

class TestVsockLLMClient:
    def test_create_message_builds_correct_request(self):
        """Verify the request payload sent over vsock."""
        from ndai.enclave.vsock_llm_client import VsockLLMClient

        client = VsockLLMClient(model="claude-sonnet-4-20250514")

        # Capture what gets sent
        sent_payload = {}

        def mock_roundtrip(payload):
            sent_payload.update(payload)
            return {
                "content": [{"type": "text", "text": "Hello"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }

        client._vsock_roundtrip = mock_roundtrip

        client.create_message(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hi"}],
            tools=[{"name": "test_tool", "description": "A test", "input_schema": {}}],
            tool_choice={"type": "tool", "name": "test_tool"},
            max_tokens=1024,
        )

        assert sent_payload["action"] == "llm_call"
        assert sent_payload["model"] == "claude-sonnet-4-20250514"
        assert sent_payload["system"] == "You are helpful."
        assert sent_payload["messages"] == [{"role": "user", "content": "Hi"}]
        assert sent_payload["max_tokens"] == 1024
        assert sent_payload["tools"] == [{"name": "test_tool", "description": "A test", "input_schema": {}}]
        assert sent_payload["tool_choice"] == {"type": "tool", "name": "test_tool"}

    def test_create_message_parses_text_response(self):
        """Parse a text-only response."""
        from ndai.enclave.vsock_llm_client import VsockLLMClient

        client = VsockLLMClient()
        client._vsock_roundtrip = lambda _: {
            "content": [{"type": "text", "text": "The answer is 42."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

        response = client.create_message(
            system="", messages=[{"role": "user", "content": "What?"}]
        )

        assert client.extract_text(response) == "The answer is 42."
        assert client.extract_tool_use(response) is None
        assert response.stop_reason == "end_turn"

    def test_create_message_parses_tool_use_response(self):
        """Parse a response with tool_use."""
        from ndai.enclave.vsock_llm_client import VsockLLMClient

        client = VsockLLMClient()
        client._vsock_roundtrip = lambda _: {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu_123",
                    "name": "make_disclosure",
                    "input": {"summary": "A great invention", "disclosed_value": 0.6},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        response = client.create_message(
            system="", messages=[{"role": "user", "content": "Disclose"}]
        )

        tool = client.extract_tool_use(response)
        assert tool is not None
        assert tool["name"] == "make_disclosure"
        assert tool["id"] == "tu_123"
        assert tool["input"]["disclosed_value"] == 0.6

    def test_create_message_raises_on_error_response(self):
        """Proxy returns an error dict."""
        from ndai.enclave.vsock_llm_client import VsockLLMClient, VsockLLMError

        client = VsockLLMClient()
        client._vsock_roundtrip = lambda _: {
            "error": "API error 429: Rate limited"
        }

        with pytest.raises(VsockLLMError, match="Rate limited"):
            client.create_message(
                system="", messages=[{"role": "user", "content": "Hi"}]
            )

    def test_create_message_raises_on_transport_error(self):
        """Transport failure raises VsockLLMError."""
        from ndai.enclave.vsock_llm_client import VsockLLMClient, VsockLLMError

        client = VsockLLMClient()
        client._vsock_roundtrip = MagicMock(
            side_effect=ConnectionError("vsock closed")
        )

        with pytest.raises(VsockLLMError, match="vsock transport error"):
            client.create_message(
                system="", messages=[{"role": "user", "content": "Hi"}]
            )

    def test_clean_messages_handles_content_blocks(self):
        """_clean_messages serializes ContentBlock objects."""
        from ndai.enclave.vsock_llm_client import ContentBlock, VsockLLMClient

        block = ContentBlock(type="text", text="Hello")
        messages = [{"role": "assistant", "content": [block]}]

        cleaned = VsockLLMClient._clean_messages(messages)
        assert cleaned[0]["content"] == [{"type": "text", "text": "Hello"}]

    def test_content_block_model_dump_text(self):
        """ContentBlock.model_dump() for text type."""
        from ndai.enclave.vsock_llm_client import ContentBlock

        block = ContentBlock(type="text", text="Hello world")
        assert block.model_dump() == {"type": "text", "text": "Hello world"}

    def test_content_block_model_dump_tool_use(self):
        """ContentBlock.model_dump() for tool_use type."""
        from ndai.enclave.vsock_llm_client import ContentBlock

        block = ContentBlock(
            type="tool_use", id="tu_1", name="test", input={"key": "val"}
        )
        dumped = block.model_dump()
        assert dumped["type"] == "tool_use"
        assert dumped["id"] == "tu_1"
        assert dumped["name"] == "test"
        assert dumped["input"] == {"key": "val"}

    def test_vsock_message_from_api_dict_mixed_content(self):
        """VsockMessage.from_api_dict handles text + tool_use blocks."""
        from ndai.enclave.vsock_llm_client import VsockMessage

        msg = VsockMessage.from_api_dict({
            "content": [
                {"type": "text", "text": "Thinking..."},
                {"type": "tool_use", "id": "tu_1", "name": "calc", "input": {"x": 1}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 50, "output_tokens": 25},
        })

        assert len(msg.content) == 2
        assert msg.content[0].type == "text"
        assert msg.content[0].text == "Thinking..."
        assert msg.content[1].type == "tool_use"
        assert msg.content[1].name == "calc"
        assert msg.stop_reason == "tool_use"
        assert msg.usage.input_tokens == 50

    def test_optional_fields_omitted_in_request(self):
        """When tools/tool_choice are None, they are not in the request."""
        from ndai.enclave.vsock_llm_client import VsockLLMClient

        client = VsockLLMClient()
        sent = {}
        client._vsock_roundtrip = lambda p: (sent.update(p) or {
            "content": [], "stop_reason": "end_turn", "usage": {}
        })

        client.create_message(system="", messages=[{"role": "user", "content": "Hi"}])

        assert "tools" not in sent
        assert "tool_choice" not in sent


# ---------------------------------------------------------------------------
# VsockProxy tests
# ---------------------------------------------------------------------------

class TestVsockProxy:
    def test_init_requires_api_key(self):
        """Proxy requires a non-empty API key."""
        from ndai.enclave.vsock_proxy import VsockProxy

        with pytest.raises(ValueError, match="API key"):
            VsockProxy(api_key="")

    def test_serialize_response_text(self):
        """_serialize_response handles text-only responses."""
        from ndai.enclave.vsock_proxy import VsockProxy

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Hello world"

        usage = MagicMock()
        usage.input_tokens = 10
        usage.output_tokens = 5

        response = MagicMock()
        response.content = [text_block]
        response.stop_reason = "end_turn"
        response.usage = usage

        result = VsockProxy._serialize_response(response)

        assert result["content"] == [{"type": "text", "text": "Hello world"}]
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5

    def test_serialize_response_tool_use(self):
        """_serialize_response handles tool_use blocks."""
        from ndai.enclave.vsock_proxy import VsockProxy

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tu_abc"
        tool_block.name = "make_offer"
        tool_block.input = {"price": 0.5}

        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50

        response = MagicMock()
        response.content = [tool_block]
        response.stop_reason = "tool_use"
        response.usage = usage

        result = VsockProxy._serialize_response(response)

        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "tool_use"
        assert result["content"][0]["name"] == "make_offer"
        assert result["content"][0]["input"] == {"price": 0.5}
        assert result["content"][0]["id"] == "tu_abc"

    @pytest.mark.asyncio
    async def test_process_request_unknown_action(self):
        """Unknown actions return an error."""
        from ndai.enclave.vsock_proxy import VsockProxy

        proxy = VsockProxy(api_key="sk-test-key")
        result = await proxy._process_request({"action": "unknown_thing"})

        assert "error" in result
        assert "Unknown action" in result["error"]

    @pytest.mark.asyncio
    async def test_process_request_llm_call(self):
        """Successful LLM call returns serialized response."""
        from ndai.enclave.vsock_proxy import VsockProxy

        proxy = VsockProxy(api_key="sk-test-key")

        # Mock the Anthropic client
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Response text"
        usage = MagicMock()
        usage.input_tokens = 10
        usage.output_tokens = 5
        mock_response = MagicMock()
        mock_response.content = [text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = usage

        proxy._client = MagicMock()
        proxy._client.messages.create.return_value = mock_response

        request = {
            "action": "llm_call",
            "model": "claude-sonnet-4-20250514",
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1024,
        }

        result = await proxy._process_request(request)

        assert "error" not in result
        assert result["content"] == [{"type": "text", "text": "Response text"}]
        assert result["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_process_request_api_error(self):
        """API errors are caught and returned as error responses."""
        import anthropic

        from ndai.enclave.vsock_proxy import VsockProxy

        proxy = VsockProxy(api_key="sk-test-key")
        proxy._client = MagicMock()

        # Simulate an API error
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        error = anthropic.APIStatusError(
            message="Rate limited",
            response=mock_response,
            body={"error": {"message": "Rate limited"}},
        )
        proxy._client.messages.create.side_effect = error

        request = {
            "action": "llm_call",
            "model": "test",
            "system": "",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
        }

        result = await proxy._process_request(request)

        assert "error" in result
        assert "429" in result["error"] or "Rate limited" in result["error"]


# ---------------------------------------------------------------------------
# Enclave app tests
# ---------------------------------------------------------------------------

class TestEnclaveApp:
    def test_parse_negotiation_request(self):
        """Valid request parses into SessionConfig."""
        from ndai.enclave.app import _parse_negotiation_request

        request = _make_negotiation_request()
        config = _parse_negotiation_request(request)

        assert config.invention.title == "Test Invention"
        assert config.invention.self_assessed_value == 0.75
        assert config.invention.outside_option_value == 0.3
        assert config.budget_cap == 0.5
        assert config.security_params.k == 3
        assert config.security_params.p == 0.5
        assert config.security_params.c == 1.0
        assert config.max_rounds == 3
        assert config.anthropic_api_key == ""  # Never set inside enclave

    def test_parse_negotiation_request_defaults(self):
        """Missing optional fields get defaults."""
        from ndai.enclave.app import _parse_negotiation_request

        request = {
            "action": "negotiate",
            "invention": {
                "title": "Minimal",
                "full_description": "Desc",
                "technical_domain": "software",
                "novelty_claims": ["New"],
                "development_stage": "concept",
                "self_assessed_value": 0.5,
                "outside_option_value": 0.2,
            },
            "budget_cap": 0.3,
            "security_params": {"k": 1, "p": 0.5, "c": 1.0},
        }

        config = _parse_negotiation_request(request)
        assert config.invention.prior_art_known == []
        assert config.invention.potential_applications == []
        assert config.invention.confidential_sections == []
        assert config.invention.max_disclosure_fraction == 1.0
        assert config.max_rounds == 5
        assert config.security_params.gamma == 1.0

    def test_parse_negotiation_request_invalid(self):
        """Invalid request raises an appropriate error."""
        from ndai.enclave.app import _parse_negotiation_request

        with pytest.raises((KeyError, ValueError, TypeError)):
            _parse_negotiation_request({"action": "negotiate"})  # Missing fields

    def test_serialize_result(self):
        """NegotiationResult serializes to a JSON-safe dict."""
        from ndai.enclave.app import _serialize_result

        result = NegotiationResult(
            outcome=NegotiationOutcomeType.AGREEMENT,
            final_price=0.4,
            omega_hat=0.6,
            theta=0.65,
            phi=1.0,
            seller_payoff=0.45,
            buyer_payoff=0.2,
            reason="Nash bargaining equilibrium reached",
        )

        d = _serialize_result(result)
        assert d["outcome"] == "agreement"
        assert d["final_price"] == 0.4
        assert d["omega_hat"] == 0.6
        # Must be JSON-serializable
        json.dumps(d)

    def test_handle_request_ping(self):
        """Ping action returns pong."""
        from ndai.enclave.app import _handle_request

        result = _handle_request({"action": "ping"})
        assert result["status"] == "ok"
        assert result["action"] == "pong"

    def test_handle_request_unknown_action(self):
        """Unknown action returns error."""
        from ndai.enclave.app import _handle_request

        result = _handle_request({"action": "explode"})
        assert result["status"] == "error"
        assert "Unknown action" in result["error"]

    def test_handle_negotiate_invalid_request(self):
        """Invalid negotiation request returns error."""
        from ndai.enclave.app import _handle_negotiate

        result = _handle_negotiate({"action": "negotiate"})
        assert result["status"] == "error"
        assert "Invalid request" in result["error"]

    def test_handle_attestation_stub(self):
        """Attestation returns stub when NSM is unavailable."""
        from ndai.enclave.app import _handle_attestation, _state

        # Ensure state is initialized (keypair generated)
        _state.initialize()
        _state.nitro_mode = False  # Force stub mode

        result = _handle_attestation({"nonce": "abc123"})
        assert result["status"] == "ok"
        # New format returns attestation_doc (base64 COSE Sign1) or legacy format
        assert "attestation_doc" in result or "attestation" in result

    def test_handle_deliver_key(self):
        """Encrypted API key should be decryptable by enclave."""
        import base64

        from ndai.enclave.app import _handle_deliver_key, _handle_request, _state
        from ndai.enclave.ephemeral_keys import encrypt_api_key

        _state.initialize()
        _state.api_key = None  # Reset

        # Encrypt a test API key for the enclave's public key
        api_key = "sk-test-deliver-123"
        encrypted = encrypt_api_key(_state.keypair.public_key_der, api_key)
        b64_payload = base64.b64encode(encrypted).decode("ascii")

        result = _handle_request({
            "action": "deliver_key",
            "encrypted_key": b64_payload,
        })
        assert result["status"] == "ok"
        assert _state.api_key == api_key

    def test_handle_deliver_key_no_keypair(self):
        """Key delivery without keypair should fail."""
        from ndai.enclave.app import _handle_deliver_key, _state

        saved_kp = _state.keypair
        _state.keypair = None
        try:
            result = _handle_deliver_key({"encrypted_key": "dGVzdA=="})
            assert result["status"] == "error"
            assert "keypair" in result["error"].lower() or "not initialized" in result["error"].lower()
        finally:
            _state.keypair = saved_kp

    def test_enclave_negotiation_session_uses_vsock_client(self):
        """EnclaveNegotiationSession uses VsockLLMClient in non-Nitro mode."""
        from ndai.enclave.app import EnclaveNegotiationSession, _state
        from ndai.enclave.vsock_llm_client import VsockLLMClient

        # Ensure we're in non-Nitro mode with no API key
        _state.initialize()
        _state.nitro_mode = False
        _state.api_key = None

        config = SessionConfig(
            invention=_make_invention(),
            budget_cap=0.5,
            security_params=SecurityParams(k=3, p=0.5, c=1.0),
            max_rounds=3,
        )

        session = EnclaveNegotiationSession(config)

        # Verify the agents got a VsockLLMClient
        assert isinstance(session.seller_agent.llm, VsockLLMClient)
        assert isinstance(session.buyer_agent.llm, VsockLLMClient)

    def test_enclave_negotiation_session_computes_params(self):
        """EnclaveNegotiationSession computes phi and theta correctly."""
        from ndai.enclave.app import EnclaveNegotiationSession
        from ndai.enclave.negotiation.engine import compute_theta, security_capacity

        sp = SecurityParams(k=3, p=0.5, c=1.0)
        config = SessionConfig(
            invention=_make_invention(outside_option_value=0.4),
            budget_cap=0.5,
            security_params=sp,
            max_rounds=3,
        )

        session = EnclaveNegotiationSession(config)

        assert session.phi == pytest.approx(security_capacity(sp))
        assert session.theta == pytest.approx(compute_theta(0.4))


# ---------------------------------------------------------------------------
# Frame protocol tests
# ---------------------------------------------------------------------------

class TestFrameProtocol:
    def test_recv_exact(self):
        """_recv_exact reads exactly the requested bytes."""
        from ndai.enclave.app import _recv_exact

        sock = MagicMock()
        # Simulate receiving data in two chunks
        sock.recv.side_effect = [b"hel", b"lo"]
        result = _recv_exact(sock, 5)
        assert result == b"hello"

    def test_recv_exact_connection_closed(self):
        """_recv_exact raises on premature close."""
        from ndai.enclave.app import _recv_exact

        sock = MagicMock()
        sock.recv.return_value = b""

        with pytest.raises(ConnectionError, match="closed"):
            _recv_exact(sock, 5)

    def test_read_frame(self):
        """_read_frame reads a length-prefixed JSON payload."""
        from ndai.enclave.app import _read_frame

        data = {"action": "ping"}
        payload = json.dumps(data).encode("utf-8")
        frame = struct.pack(">I", len(payload)) + payload

        sock = MagicMock()
        # Return the full frame in one recv call for simplicity
        sock.recv.side_effect = [frame[:4], payload]

        result = _read_frame(sock)
        assert result == data

    def test_read_frame_rejects_oversized(self):
        """_read_frame rejects payloads over MAX_PAYLOAD_BYTES."""
        from ndai.enclave.app import MAX_PAYLOAD_BYTES, _read_frame

        sock = MagicMock()
        # Send a length header that exceeds the limit
        oversized_length = MAX_PAYLOAD_BYTES + 1
        sock.recv.return_value = struct.pack(">I", oversized_length)

        with pytest.raises(ValueError, match="too large"):
            _read_frame(sock)

    def test_write_frame(self):
        """_write_frame sends length-prefixed JSON."""
        from ndai.enclave.app import _write_frame

        sock = MagicMock()
        data = {"status": "ok", "result": 42}

        _write_frame(sock, data)

        sent = sock.sendall.call_args[0][0]
        length = struct.unpack(">I", sent[:4])[0]
        payload = json.loads(sent[4:].decode("utf-8"))

        assert length == len(sent) - 4
        assert payload == data


# ---------------------------------------------------------------------------
# Round-trip integration test (VsockLLMClient <-> VsockProxy, mocked socket)
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_client_request_matches_proxy_expectation(self):
        """Verify the VsockLLMClient request format is what VsockProxy expects."""
        from ndai.enclave.vsock_llm_client import VsockLLMClient

        client = VsockLLMClient(model="claude-sonnet-4-20250514")

        captured_request = {}
        def mock_roundtrip(payload):
            captured_request.update(payload)
            return {
                "content": [{"type": "text", "text": "OK"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }

        client._vsock_roundtrip = mock_roundtrip

        tools = [{"name": "test_tool", "description": "desc", "input_schema": {"type": "object"}}]
        client.create_message(
            system="sys",
            messages=[{"role": "user", "content": "msg"}],
            tools=tools,
            tool_choice={"type": "tool", "name": "test_tool"},
            max_tokens=512,
        )

        # These are the fields the proxy expects
        assert captured_request["action"] == "llm_call"
        assert "model" in captured_request
        assert "system" in captured_request
        assert "messages" in captured_request
        assert "max_tokens" in captured_request
        assert "tools" in captured_request
        assert "tool_choice" in captured_request

    def test_proxy_response_parseable_by_client(self):
        """VsockProxy._serialize_response output can be parsed by VsockMessage."""
        from ndai.enclave.vsock_llm_client import VsockMessage
        from ndai.enclave.vsock_proxy import VsockProxy

        # Create a mock Anthropic response
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Reasoning..."

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tu_xyz"
        tool_block.name = "make_offer"
        tool_block.input = {"price": 0.42, "explanation": "Fair price"}

        usage = MagicMock()
        usage.input_tokens = 200
        usage.output_tokens = 100

        api_response = MagicMock()
        api_response.content = [text_block, tool_block]
        api_response.stop_reason = "tool_use"
        api_response.usage = usage

        # Serialize via proxy
        serialized = VsockProxy._serialize_response(api_response)

        # Parse via client
        msg = VsockMessage.from_api_dict(serialized)

        assert len(msg.content) == 2
        assert msg.content[0].type == "text"
        assert msg.content[0].text == "Reasoning..."
        assert msg.content[1].type == "tool_use"
        assert msg.content[1].name == "make_offer"
        assert msg.content[1].input["price"] == 0.42
        assert msg.stop_reason == "tool_use"
        assert msg.usage.input_tokens == 200


# ---------------------------------------------------------------------------
# NitroEnclaveProvider single-connection protocol tests
# ---------------------------------------------------------------------------

class TestNitroEnclaveProviderProtocol:
    """Verify send_message/receive_message use a single vsock connection.

    The enclave app uses single-connection request-response: it accepts one
    connection, reads the request, writes the response, and closes. The
    provider must keep the connection open between send and receive.
    """

    def _make_provider_with_enclave(self):
        """Set up a NitroEnclaveProvider with a fake active enclave."""
        from ndai.tee.nitro_provider import NitroEnclaveProvider
        from ndai.tee.provider import EnclaveConfig, EnclaveIdentity, TEEType

        provider = NitroEnclaveProvider()
        identity = EnclaveIdentity(
            enclave_id="enc-test-123",
            enclave_cid=42,
            pcr0="aaa",
            pcr1="bbb",
            pcr2="ccc",
            tee_type=TEEType.NITRO,
        )
        config = EnclaveConfig(cpu_count=2, memory_mib=1600, eif_path="test.eif")
        provider._active_enclaves["enc-test-123"] = identity
        provider._enclave_configs["enc-test-123"] = config
        return provider

    @pytest.mark.asyncio
    async def test_send_message_stores_connection(self):
        """send_message should open a socket and store it for receive_message."""
        provider = self._make_provider_with_enclave()

        mock_sock = MagicMock(spec=socket.socket)
        with patch("ndai.tee.nitro_provider.socket.socket", return_value=mock_sock):
            await provider.send_message("enc-test-123", {"action": "ping"})

        # Connection should be stored
        assert "enc-test-123" in provider._connections
        assert provider._connections["enc-test-123"] is mock_sock
        # Socket should NOT have been closed
        mock_sock.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_receive_message_uses_stored_connection(self):
        """receive_message should read from the socket opened by send_message."""
        provider = self._make_provider_with_enclave()

        # Prepare a response frame
        response_data = {"status": "ok", "action": "pong"}
        payload = json.dumps(response_data).encode("utf-8")
        frame = struct.pack(">I", len(payload)) + payload

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.recv.side_effect = [frame[:4], payload]

        # Simulate send_message having stored the connection
        provider._connections["enc-test-123"] = mock_sock

        result = await provider.receive_message("enc-test-123")

        assert result == response_data
        # Connection should have been removed and closed
        assert "enc-test-123" not in provider._connections
        mock_sock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_without_send_raises(self):
        """receive_message without prior send_message should raise."""
        from ndai.tee.provider import TEEError

        provider = self._make_provider_with_enclave()

        with pytest.raises(TEEError, match="No open connection"):
            await provider.receive_message("enc-test-123")

    @pytest.mark.asyncio
    async def test_send_receive_same_socket(self):
        """send_message and receive_message must use the same socket object."""
        provider = self._make_provider_with_enclave()

        response_data = {"status": "ok", "result": {"outcome": "agreement"}}
        payload = json.dumps(response_data).encode("utf-8")
        frame = struct.pack(">I", len(payload)) + payload

        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.recv.side_effect = [frame[:4], payload]

        with patch("ndai.tee.nitro_provider.socket.socket", return_value=mock_sock):
            await provider.send_message("enc-test-123", {"action": "negotiate"})
            stored_sock = provider._connections["enc-test-123"]
            result = await provider.receive_message("enc-test-123")

        # The socket used for receive must be the same one from send
        assert stored_sock is mock_sock
        assert result == response_data

    @pytest.mark.asyncio
    async def test_send_closes_stale_connection(self):
        """A second send_message should close the previous connection."""
        provider = self._make_provider_with_enclave()

        stale_sock = MagicMock(spec=socket.socket)
        provider._connections["enc-test-123"] = stale_sock

        new_sock = MagicMock(spec=socket.socket)
        with patch("ndai.tee.nitro_provider.socket.socket", return_value=new_sock):
            await provider.send_message("enc-test-123", {"action": "ping"})

        # Stale connection should have been closed
        stale_sock.close.assert_called_once()
        # New connection should be stored
        assert provider._connections["enc-test-123"] is new_sock

    @pytest.mark.asyncio
    async def test_terminate_closes_connection(self):
        """terminate_enclave should close any stored connection."""
        provider = self._make_provider_with_enclave()

        mock_sock = MagicMock(spec=socket.socket)
        provider._connections["enc-test-123"] = mock_sock

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            await provider.terminate_enclave("enc-test-123")

        mock_sock.close.assert_called_once()
        assert "enc-test-123" not in provider._connections
