"""E2E tests for Conditional Recall API."""

import asyncio
import os
from unittest.mock import patch

import asyncpg
import pytest
from fastapi.testclient import TestClient

from ndai.api.app import create_app
from ndai.enclave.sessions.secret_proxy import SecretProxyResult

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


def test_create_and_list_secret(client):
    token = _register(client, "owner@test.com")
    res = client.post("/api/v1/secrets/", json={
        "name": "AWS Key",
        "description": "Production AWS access key",
        "secret_value": "AKIAIOSFODNN7EXAMPLE",
        "policy": {"allowed_actions": ["list S3 buckets", "read S3 objects"], "max_uses": 3},
    }, headers=_auth(token))
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "AWS Key"
    assert data["uses_remaining"] == 3
    assert "secret_value" not in str(data)

    res = client.get("/api/v1/secrets/", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_available_secrets_hides_value(client):
    owner_token = _register(client, "owner2@test.com")
    consumer_token = _register(client, "consumer@test.com", role="buyer")

    client.post("/api/v1/secrets/", json={
        "name": "API Token",
        "secret_value": "secret-token-value",
        "policy": {"allowed_actions": ["query API"], "max_uses": 1},
    }, headers=_auth(owner_token))

    res = client.get("/api/v1/secrets/available", headers=_auth(consumer_token))
    assert res.status_code == 200
    secrets = res.json()
    assert len(secrets) == 1
    assert secrets[0]["name"] == "API Token"
    assert "secret-token-value" not in str(secrets)


def _mock_proxy_result(**overrides):
    defaults = dict(
        success=True,
        result_text='{"items": ["bucket-a", "bucket-b"]}',
        action_validated=True,
        secret_deleted=True,
        policy_report={"all_passed": True, "results": [], "policy_hash": "abc123"},
        policy_constraints=[],
        egress_log=[],
        verification={"session_id": "test", "events": [], "chain_hashes": [], "final_hash": "def456", "attestation_claims": []},
    )
    defaults.update(overrides)
    return SecretProxyResult(**defaults)


def test_use_secret_valid_action(client):
    owner_token = _register(client, "owner3@test.com")
    consumer_token = _register(client, "consumer3@test.com", role="buyer")

    res = client.post("/api/v1/secrets/", json={
        "name": "Test Key",
        "secret_value": "sk-test-12345",
        "policy": {"allowed_actions": ["list items"], "max_uses": 2},
    }, headers=_auth(owner_token))
    secret_id = res.json()["id"]

    with patch("ndai.api.routers.secrets.SecretProxySession") as MockSession:
        MockSession.return_value.run.return_value = _mock_proxy_result()
        res = client.post(f"/api/v1/secrets/{secret_id}/use", json={
            "action": "list items",
        }, headers=_auth(consumer_token))
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["secret_name"] == "Test Key"


def test_use_secret_invalid_action(client):
    owner_token = _register(client, "owner4@test.com")
    consumer_token = _register(client, "consumer4@test.com", role="buyer")

    res = client.post("/api/v1/secrets/", json={
        "name": "Restricted Key",
        "secret_value": "sk-restricted",
        "policy": {"allowed_actions": ["read only"], "max_uses": 5},
    }, headers=_auth(owner_token))
    secret_id = res.json()["id"]

    res = client.post(f"/api/v1/secrets/{secret_id}/use", json={
        "action": "delete everything",
    }, headers=_auth(consumer_token))
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False


def test_access_log(client):
    owner_token = _register(client, "owner5@test.com")
    consumer_token = _register(client, "consumer5@test.com", role="buyer")

    res = client.post("/api/v1/secrets/", json={
        "name": "Logged Key",
        "secret_value": "sk-logged",
        "policy": {"allowed_actions": ["read"], "max_uses": 5},
    }, headers=_auth(owner_token))
    secret_id = res.json()["id"]

    client.post(f"/api/v1/secrets/{secret_id}/use", json={"action": "write"}, headers=_auth(consumer_token))

    res = client.get(f"/api/v1/secrets/{secret_id}/access-log", headers=_auth(owner_token))
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) == 1
    assert logs[0]["status"] == "denied"

    res = client.get(f"/api/v1/secrets/{secret_id}/access-log", headers=_auth(consumer_token))
    assert res.status_code == 403


def test_owner_cannot_use_own_secret(client):
    token = _register(client, "owner6@test.com")
    res = client.post("/api/v1/secrets/", json={
        "name": "Self-Use Key",
        "secret_value": "sk-self",
        "policy": {"allowed_actions": ["read"], "max_uses": 5},
    }, headers=_auth(token))
    secret_id = res.json()["id"]

    res = client.post(f"/api/v1/secrets/{secret_id}/use", json={"action": "read"}, headers=_auth(token))
    assert res.status_code == 403


def test_depleted_secret_returns_400(client):
    owner_token = _register(client, "owner7@test.com")
    consumer_token = _register(client, "consumer7@test.com", role="buyer")

    res = client.post("/api/v1/secrets/", json={
        "name": "One-Use Key",
        "secret_value": "sk-oneuse",
        "policy": {"allowed_actions": ["read"], "max_uses": 1},
    }, headers=_auth(owner_token))
    secret_id = res.json()["id"]

    with patch("ndai.api.routers.secrets.SecretProxySession") as MockSession:
        MockSession.return_value.run.return_value = _mock_proxy_result()
        res = client.post(f"/api/v1/secrets/{secret_id}/use", json={"action": "read"}, headers=_auth(consumer_token))
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Second use should fail — secret is depleted
    res = client.post(f"/api/v1/secrets/{secret_id}/use", json={"action": "read"}, headers=_auth(consumer_token))
    assert res.status_code == 400


def test_revoke_secret(client):
    owner_token = _register(client, "owner8@test.com")
    consumer_token = _register(client, "consumer8@test.com", role="buyer")

    res = client.post("/api/v1/secrets/", json={
        "name": "Revocable Key",
        "secret_value": "sk-revocable",
        "policy": {"allowed_actions": ["read"], "max_uses": 5},
    }, headers=_auth(owner_token))
    secret_id = res.json()["id"]

    # Revoke
    res = client.post(f"/api/v1/secrets/{secret_id}/revoke", headers=_auth(owner_token))
    assert res.status_code == 200
    assert res.json()["status"] == "revoked"

    # Cannot use after revocation
    res = client.post(f"/api/v1/secrets/{secret_id}/use", json={"action": "read"}, headers=_auth(consumer_token))
    assert res.status_code == 400
