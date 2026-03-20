"""Tests for SecretProxySession."""

from unittest.mock import patch

from ndai.enclave.sessions.secret_proxy import (
    SecretProxyConfig,
    SecretProxyResult,
    SecretProxySession,
)


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

    with patch.object(session, "_call_llm") as mock_llm:
        mock_llm.return_value = "Found 3 buckets: prod-data, staging-logs, backups"
        result = session.run()

    assert result.success is True
    assert "buckets" in result.result_text
    assert result.secret_deleted is True


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

    with patch.object(session, "_call_llm") as mock_llm:
        mock_llm.return_value = "result"
        session.run()

    assert session.config.secret_value is None
