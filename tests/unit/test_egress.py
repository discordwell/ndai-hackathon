"""Tests for egress logging module."""

from unittest.mock import MagicMock

from ndai.enclave.egress import (
    EgressAwareLLMClient,
    EgressEntry,
    EgressLog,
    _sha256_of,
)


class TestEgressEntry:
    def test_creation(self):
        e = EgressEntry(
            timestamp="2025-01-01T00:00:00Z",
            endpoint="api.openai.com/v1/chat/completions",
            method="POST",
            request_bytes=100,
            response_bytes=200,
            request_hash="abc123",
            response_hash="def456",
        )
        assert e.request_bytes == 100
        assert e.endpoint == "api.openai.com/v1/chat/completions"


class TestEgressLog:
    def test_record_and_to_dict(self):
        log = EgressLog()
        entry = EgressEntry(
            timestamp="2025-01-01T00:00:00Z",
            endpoint="test",
            method="POST",
            request_bytes=10,
            response_bytes=20,
            request_hash="h1",
            response_hash="h2",
        )
        log.record(entry)
        dicts = log.to_dict_list()
        assert len(dicts) == 1
        assert dicts[0]["request_hash"] == "h1"

    def test_empty_log(self):
        log = EgressLog()
        assert log.to_dict_list() == []


class TestHashCorrectness:
    def test_sha256_deterministic(self):
        h1 = _sha256_of("hello")
        h2 = _sha256_of("hello")
        assert h1 == h2
        assert len(h1) == 64

    def test_different_input_different_hash(self):
        assert _sha256_of("a") != _sha256_of("b")


class TestEgressAwareLLMClient:
    def test_wraps_and_logs_call(self):
        mock_client = MagicMock()
        mock_client.model = "gpt-4o"
        mock_client.create_message.return_value = "mock_response"
        mock_client.extract_text.return_value = "hello"

        log = EgressLog()
        wrapper = EgressAwareLLMClient(mock_client, log)

        response = wrapper.create_message(system="sys", messages=[])
        assert response == "mock_response"
        assert len(log.entries) == 1
        assert log.entries[0].method == "POST"
        assert len(log.entries[0].request_hash) == 64

    def test_extract_text_delegates(self):
        mock_client = MagicMock()
        mock_client.extract_text.return_value = "text"
        wrapper = EgressAwareLLMClient(mock_client, EgressLog())
        assert wrapper.extract_text("resp") == "text"

    def test_openai_endpoint_detection(self):
        mock_client = MagicMock()
        mock_client.__class__.__name__ = "OpenAILLMClient"
        mock_client.model = "gpt-4o"
        mock_client.create_message.return_value = "resp"

        log = EgressLog()
        wrapper = EgressAwareLLMClient(mock_client, log)
        wrapper.create_message(system="s", messages=[])
        assert "openai" in log.entries[0].endpoint

    def test_anthropic_endpoint_detection(self):
        mock_client = MagicMock()
        mock_client.__class__.__name__ = "LLMClient"
        mock_client.model = "claude-sonnet"
        mock_client.create_message.return_value = "resp"

        log = EgressLog()
        wrapper = EgressAwareLLMClient(mock_client, log)
        wrapper.create_message(system="s", messages=[])
        assert "anthropic" in log.entries[0].endpoint
