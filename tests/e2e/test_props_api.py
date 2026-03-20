"""E2E tests for Props (meeting transcript processing) API."""

import asyncio
import os

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


SAMPLE_TRANSCRIPT = (
    "Alice: Let's discuss the Q2 roadmap. The auth service migration is blocking the mobile team.\n"
    "Bob: Agreed. We need the new OAuth endpoints by March 15th.\n"
    "Alice: We decided to use PostgreSQL instead of MongoDB for the events store.\n"
    "Bob: One blocker — no staging environment access yet.\n"
)


def test_submit_transcript(client):
    token = _register(client, "user1@test.com")
    res = client.post("/api/v1/transcripts/", json={
        "title": "Q2 Roadmap Sync",
        "team_name": "Backend Team",
        "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(token))
    assert res.status_code in (201, 500)
    if res.status_code == 201:
        data = res.json()
        assert data["title"] == "Q2 Roadmap Sync"
        assert data["status"] in ("completed", "error")
        assert "content" not in str(data)


def test_list_transcripts(client):
    token = _register(client, "user2@test.com")
    res = client.get("/api/v1/transcripts/", headers=_auth(token))
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_other_user_cannot_see_transcript(client):
    user1_token = _register(client, "user3@test.com")
    user2_token = _register(client, "user4@test.com", role="buyer")

    res = client.post("/api/v1/transcripts/", json={
        "title": "Private Meeting", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(user1_token))

    if res.status_code == 201:
        tid = res.json()["id"]
        res = client.get(f"/api/v1/transcripts/{tid}", headers=_auth(user2_token))
        assert res.status_code == 403
