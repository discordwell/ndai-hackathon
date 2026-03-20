"""E2E tests for TrustKit verification chain, policy enforcement, and egress logging.

These tests verify that API responses include verification, policy, and egress data.
They use mocked LLM calls (no real API key needed).
"""

import asyncio
import os
from unittest.mock import patch, MagicMock

import asyncpg
import pytest
from fastapi.testclient import TestClient

from ndai.api.app import create_app

_DB_URL = os.environ.get("DATABASE_URL", "postgresql://ndai:ndai@localhost:5432/ndai").replace("+asyncpg", "")
_TRUNCATE_SQL = """
TRUNCATE TABLE secret_access_log, secrets, transcript_summaries, meeting_transcripts,
               agreement_outcomes, audit_log, payments, agreements, inventions, users CASCADE;
"""


def _clean_db():
    async def _truncate():
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(_TRUNCATE_SQL)
        finally:
            await conn.close()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_truncate())
    finally:
        loop.close()


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean():
    _clean_db()
    yield


def _register(client, email, role="seller"):
    res = client.post("/api/v1/auth/register", json={
        "email": email, "password": "testpass123", "role": role, "display_name": f"Test {role}",
    })
    assert res.status_code == 200
    return res.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _mock_llm_client():
    """Create a mock that works as both raw client and egress-wrapped client."""
    mock = MagicMock()
    mock.model = "gpt-4o-mock"
    mock.create_message.return_value = "resp"
    mock.extract_text.return_value = '{"result": "simulated API output", "status": "ok"}'
    return mock


class TestSecretVerification:
    def test_denied_action_includes_verification(self, client):
        """Denied actions should still have verification chain."""
        owner_token = _register(client, "vowner1@test.com")
        consumer_token = _register(client, "vconsumer1@test.com", role="buyer")

        res = client.post("/api/v1/secrets/", json={
            "name": "Verified Key",
            "secret_value": "sk-verified",
            "policy": {"allowed_actions": ["read only"], "max_uses": 5},
        }, headers=_auth(owner_token))
        secret_id = res.json()["id"]

        res = client.post(f"/api/v1/secrets/{secret_id}/use", json={
            "action": "delete everything",
        }, headers=_auth(consumer_token))
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        # Verification should be present even for denied actions
        assert data["verification"] is not None
        assert "session_id" in data["verification"]
        assert "final_hash" in data["verification"]


class TestTranscriptVerification:
    def test_summary_includes_verification_fields(self, client):
        """After transcript processing, summary should have verification data."""
        import json

        token = _register(client, "vsubmitter1@test.com")

        mock_llm_response = json.dumps({
            "executive_summary": "Team discussed Q2 roadmap priorities.",
            "action_items": ["Bob: implement auth flow"],
            "key_decisions": ["Use PostgreSQL"],
            "dependencies": ["Auth service"],
            "blockers": ["No staging access"],
            "sentiment": "neutral",
        })

        mock_client = MagicMock()
        mock_client.model = "gpt-4o-mock"
        mock_client.create_message.return_value = "resp"
        mock_client.extract_text.return_value = mock_llm_response

        with patch(
            "ndai.enclave.sessions.transcript_processor.TranscriptProcessingSession._build_client",
            return_value=mock_client,
        ):
            res = client.post("/api/v1/transcripts/", json={
                "title": "Q2 Sync",
                "team_name": "Backend",
                "content": "Alice: Let's discuss the Q2 roadmap. Bob: We need OAuth endpoints by March.",
            }, headers=_auth(token))
        assert res.status_code == 201
        transcript_id = res.json()["id"]

        # Fetch summary
        res = client.get(f"/api/v1/transcripts/{transcript_id}/summary", headers=_auth(token))
        assert res.status_code == 200
        summary = res.json()

        # Verify verification fields are present
        assert summary["verification"] is not None
        assert "session_id" in summary["verification"]
        assert "attestation_claims" in summary["verification"]
        assert len(summary["verification"]["attestation_claims"]) > 0

        # Verify policy fields
        assert summary["policy_report"] is not None
        assert "all_passed" in summary["policy_report"]
        assert "policy_hash" in summary["policy_report"]

        # Verify egress fields
        assert summary["egress_log"] is not None
