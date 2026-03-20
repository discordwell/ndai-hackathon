"""Tests for TranscriptProcessingSession."""

import json
from unittest.mock import MagicMock, patch

from ndai.enclave.sessions.transcript_processor import (
    TranscriptConfig,
    TranscriptProcessingSession,
    TranscriptResult,
)


SAMPLE_TRANSCRIPT = """
Alice: Let's discuss the Q2 roadmap. The auth service migration is blocking the mobile team.
Bob: Agreed. We need the new OAuth endpoints by March 15th. I'll handle the token refresh flow.
Alice: Great. Also, we decided to use PostgreSQL instead of MongoDB for the events store.
Bob: One blocker — we don't have staging environment access yet. DevOps ticket is open.
Alice: I'll follow up with the DevOps team today. Let's sync again Thursday.
"""


def _make_mock_client(return_text="mock result"):
    mock = MagicMock()
    mock.model = "gpt-4o"
    mock.create_message.return_value = "resp"
    mock.extract_text.return_value = return_text
    return mock


def test_transcript_processing_returns_structured_result():
    config = TranscriptConfig(
        transcript_text=SAMPLE_TRANSCRIPT,
        title="Q2 Roadmap Sync",
        team_name="Backend Team",
        llm_provider="openai",
        api_key="test-key",
        llm_model="gpt-4o",
    )
    session = TranscriptProcessingSession(config)

    mock_response = json.dumps({
        "executive_summary": "Backend team discussed Q2 roadmap priorities.",
        "action_items": ["Bob: implement token refresh flow", "Alice: follow up with DevOps"],
        "key_decisions": ["Use PostgreSQL instead of MongoDB for events store"],
        "dependencies": ["Auth service migration needed by mobile team"],
        "blockers": ["No staging environment access"],
        "sentiment": "neutral",
    })
    mock_client = _make_mock_client(mock_response)

    with patch.object(session, "_build_client", return_value=mock_client):
        result = session.run()

    assert isinstance(result, TranscriptResult)
    assert result.success is True
    assert "roadmap" in result.executive_summary.lower() or len(result.executive_summary) > 0
    assert len(result.action_items) >= 1
    assert result.transcript_deleted is True
    assert result.policy_report is not None
    assert result.verification is not None
    assert result.egress_log is not None


def test_transcript_is_cleared_after_processing():
    config = TranscriptConfig(
        transcript_text="Some private meeting content",
        title="Test",
        llm_provider="openai",
        api_key="test-key",
        llm_model="gpt-4o",
    )
    session = TranscriptProcessingSession(config)

    mock_response = json.dumps({
        "executive_summary": "Test summary",
        "action_items": [],
        "key_decisions": [],
        "dependencies": [],
        "blockers": [],
        "sentiment": "neutral",
    })
    mock_client = _make_mock_client(mock_response)

    with patch.object(session, "_build_client", return_value=mock_client):
        session.run()

    assert session.config.transcript_text is None
