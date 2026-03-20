"""Tests for SecretProxySession."""

from unittest.mock import MagicMock, patch

from ndai.enclave.sessions.secret_proxy import (
    SecretProxyConfig,
    SecretProxyResult,
    SecretProxySession,
)


def _make_mock_client(return_text="mock result"):
    mock = MagicMock()
    mock.model = "gpt-4o"
    mock.create_message.return_value = "resp"
    mock.extract_text.return_value = return_text
    return mock


def test_valid_action_succeeds():
    config = SecretProxyConfig(
        secret_value="sk-test-key-12345",
        action="list S3 buckets",
        policy={"allowed_actions": ["list S3 buckets", "read S3 objects"], "max_uses": 5},
        llm_provider="openai",
        api_key="test-key",
        llm_model="gpt-4o",
    )
    session = SecretProxySession(config)
    mock_client = _make_mock_client("Found 3 buckets: prod-data, staging-logs, backups")

    with patch.object(session, "_build_client", return_value=mock_client):
        result = session.run()

    assert result.success is True
    assert "buckets" in result.result_text
    assert result.secret_deleted is True
    assert result.policy_report is not None
    assert result.verification is not None
    assert result.egress_log is not None


def test_invalid_action_denied():
    config = SecretProxyConfig(
        secret_value="sk-test-key-12345",
        action="delete all S3 buckets",
        policy={"allowed_actions": ["list S3 buckets"], "max_uses": 5},
        llm_provider="openai",
        api_key="test-key",
        llm_model="gpt-4o",
    )
    session = SecretProxySession(config)
    result = session.run()

    assert result.success is False
    assert "not allowed" in result.result_text.lower() or "denied" in result.result_text.lower()
    assert result.action_validated is False
    assert result.verification is not None


def test_secret_is_cleared_after_run():
    config = SecretProxyConfig(
        secret_value="sk-test-key-12345",
        action="list S3 buckets",
        policy={"allowed_actions": ["list S3 buckets"], "max_uses": 5},
        llm_provider="openai",
        api_key="test-key",
        llm_model="gpt-4o",
    )
    session = SecretProxySession(config)
    mock_client = _make_mock_client("result")

    with patch.object(session, "_build_client", return_value=mock_client):
        session.run()

    assert session.config.secret_value is None
