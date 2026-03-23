"""E2E tests for Props (meeting transcript processing) API."""

import asyncio
import os
import time

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


def _wait_for_status(client, token, transcript_id, target_statuses, timeout=30):
    """Poll the transcript until status matches one of target_statuses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = client.get(f"/api/v1/transcripts/{transcript_id}", headers=_auth(token))
        assert res.status_code == 200
        status = res.json()["status"]
        if status in target_statuses:
            return status
        time.sleep(1)
    raise TimeoutError(f"Transcript {transcript_id} did not reach {target_statuses} within {timeout}s")


SAMPLE_TRANSCRIPT = (
    "Alice: Let's discuss the Q2 roadmap. The auth service migration is blocking the mobile team.\n"
    "Bob: Agreed. We need the new OAuth endpoints by March 15th.\n"
    "Alice: We decided to use PostgreSQL instead of MongoDB for the events store.\n"
    "Bob: One blocker — no staging environment access yet.\n"
)

SAMPLE_TRANSCRIPT_2 = (
    "Carol: The data pipeline needs a redesign. Current ETL is too slow for real-time dashboards.\n"
    "Dave: We're blocked on the schema migration from the backend team.\n"
    "Carol: Decision: switch from batch to streaming with Kafka.\n"
    "Dave: Action item: Carol to draft the Kafka migration proposal by Friday.\n"
)


def test_submit_returns_submitted_status(client):
    """Submit should return 201 with status 'submitted' (async processing)."""
    token = _register(client, "submit1@test.com")
    res = client.post("/api/v1/transcripts/", json={
        "title": "Q2 Roadmap Sync",
        "team_name": "Backend Team",
        "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(token))
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Q2 Roadmap Sync"
    assert data["team_name"] == "Backend Team"
    assert data["status"] == "submitted"
    assert "content" not in str(data)
    assert data["id"]


def test_list_transcripts_paginated(client):
    """List should return paginated response with items, total, offset, limit."""
    token = _register(client, "list1@test.com")
    # Submit 3 transcripts
    for i in range(3):
        client.post("/api/v1/transcripts/", json={
            "title": f"Meeting {i}", "content": SAMPLE_TRANSCRIPT,
        }, headers=_auth(token))

    res = client.get("/api/v1/transcripts/?offset=0&limit=2", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "offset" in data
    assert "limit" in data
    assert len(data["items"]) == 2
    assert data["total"] >= 3
    assert data["offset"] == 0
    assert data["limit"] == 2

    # Fetch next page
    res2 = client.get("/api/v1/transcripts/?offset=2&limit=2", headers=_auth(token))
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) >= 1


def test_other_user_cannot_see_transcript(client):
    """Ownership check: user B cannot access user A's transcript."""
    user1_token = _register(client, "owner1@test.com")
    user2_token = _register(client, "other1@test.com", role="buyer")

    res = client.post("/api/v1/transcripts/", json={
        "title": "Private Meeting", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(user1_token))
    assert res.status_code == 201
    tid = res.json()["id"]

    res = client.get(f"/api/v1/transcripts/{tid}", headers=_auth(user2_token))
    assert res.status_code == 403


def test_other_user_cannot_see_summary(client):
    """Ownership check: user B cannot access user A's summary."""
    user1_token = _register(client, "owner2@test.com")
    user2_token = _register(client, "other2@test.com", role="buyer")

    res = client.post("/api/v1/transcripts/", json={
        "title": "Secret Meeting", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(user1_token))
    assert res.status_code == 201
    tid = res.json()["id"]

    res = client.get(f"/api/v1/transcripts/{tid}/summary", headers=_auth(user2_token))
    assert res.status_code == 403


def test_get_summary_404_while_processing(client):
    """Summary should return 404 before processing completes."""
    token = _register(client, "summary404@test.com")
    res = client.post("/api/v1/transcripts/", json={
        "title": "Quick Meeting", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(token))
    assert res.status_code == 201
    tid = res.json()["id"]

    # Immediately request summary — should be 404
    res = client.get(f"/api/v1/transcripts/{tid}/summary", headers=_auth(token))
    assert res.status_code == 404


def test_get_summary_after_processing(client):
    """After processing completes, summary should have all expected fields."""
    token = _register(client, "summary_ok@test.com")
    res = client.post("/api/v1/transcripts/", json={
        "title": "Full Summary Test", "team_name": "Platform", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(token))
    assert res.status_code == 201
    tid = res.json()["id"]

    try:
        status = _wait_for_status(client, token, tid, ["completed", "error"], timeout=30)
    except TimeoutError:
        pytest.skip("TEE processing did not complete in time (likely no LLM key)")

    if status == "error":
        pytest.skip("Transcript processing failed (likely no LLM key configured)")

    res = client.get(f"/api/v1/transcripts/{tid}/summary", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert data["executive_summary"]
    assert isinstance(data["action_items"], list)
    assert isinstance(data["key_decisions"], list)
    assert isinstance(data["dependencies"], list)
    assert isinstance(data["blockers"], list)
    assert data["sentiment"] in ("positive", "neutral", "negative", "mixed", None)


def test_aggregate_requires_two_completed(client):
    """Aggregation with fewer than 2 completed transcripts should fail."""
    token = _register(client, "agg_fail@test.com")
    res = client.post("/api/v1/transcripts/", json={
        "title": "Solo Meeting", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(token))
    assert res.status_code == 201
    tid = res.json()["id"]

    # Try aggregating with just 1 transcript
    res = client.post("/api/v1/transcripts/aggregate", json={
        "transcript_ids": [tid],
    }, headers=_auth(token))
    assert res.status_code == 422  # min_length=2 validation


def test_aggregate_success(client):
    """Aggregation with 2+ completed transcripts should return cross-team report."""
    token = _register(client, "agg_ok@test.com")

    # Submit 2 transcripts
    res1 = client.post("/api/v1/transcripts/", json={
        "title": "Backend Sync", "team_name": "Backend", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(token))
    assert res1.status_code == 201
    tid1 = res1.json()["id"]

    res2 = client.post("/api/v1/transcripts/", json={
        "title": "Data Sync", "team_name": "Data", "content": SAMPLE_TRANSCRIPT_2,
    }, headers=_auth(token))
    assert res2.status_code == 201
    tid2 = res2.json()["id"]

    # Wait for both to complete
    try:
        _wait_for_status(client, token, tid1, ["completed", "error"], timeout=30)
        _wait_for_status(client, token, tid2, ["completed", "error"], timeout=30)
    except TimeoutError:
        pytest.skip("TEE processing did not complete in time")

    # Check both completed
    s1 = client.get(f"/api/v1/transcripts/{tid1}", headers=_auth(token)).json()["status"]
    s2 = client.get(f"/api/v1/transcripts/{tid2}", headers=_auth(token)).json()["status"]
    if s1 != "completed" or s2 != "completed":
        pytest.skip("One or both transcripts errored (likely no LLM key)")

    res = client.post("/api/v1/transcripts/aggregate", json={
        "transcript_ids": [tid1, tid2],
    }, headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert data["cross_team_summary"]
    assert isinstance(data["shared_dependencies"], list)
    assert isinstance(data["shared_blockers"], list)
    assert isinstance(data["recommendations"], list)
    assert data["transcript_count"] == 2


def test_other_user_cannot_aggregate(client):
    """User B cannot aggregate user A's transcripts."""
    user1_token = _register(client, "agg_owner@test.com")
    user2_token = _register(client, "agg_other@test.com", role="buyer")

    res1 = client.post("/api/v1/transcripts/", json={
        "title": "Team A Meeting", "content": SAMPLE_TRANSCRIPT,
    }, headers=_auth(user1_token))
    assert res1.status_code == 201
    tid1 = res1.json()["id"]

    res2 = client.post("/api/v1/transcripts/", json={
        "title": "Team A Meeting 2", "content": SAMPLE_TRANSCRIPT_2,
    }, headers=_auth(user1_token))
    assert res2.status_code == 201
    tid2 = res2.json()["id"]

    # User 2 tries to aggregate user 1's transcripts
    res = client.post("/api/v1/transcripts/aggregate", json={
        "transcript_ids": [tid1, tid2],
    }, headers=_auth(user2_token))
    assert res.status_code in (403, 404)
