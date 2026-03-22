"""Integration test — full ZK auth challenge-response flow.

Tests the complete lifecycle:
  1. Generate Ed25519 keypair
  2. Register identity (POST /api/v1/zk-auth/register)
  3. Request challenge nonce (POST /api/v1/zk-auth/challenge)
  4. Sign the nonce
  5. Verify signature + get JWT (POST /api/v1/zk-auth/verify)
  6. Verify JWT decodes correctly with auth_type='zk'
  7. Verify a regular JWT is rejected by get_zk_identity

Mocks: Redis (async) and database (SQLAlchemy AsyncSession).
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ndai:ndai@localhost:5432/ndai")

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from jose import jwt
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ndai.api.dependencies import create_access_token, create_zk_token
from ndai.api.routers.zk_auth import router as zk_auth_router
from ndai.config import settings


# ── Helpers ──


def _generate_ed25519_keypair():
    """Generate an Ed25519 keypair, returning (private_key, pubkey_hex)."""
    privkey = Ed25519PrivateKey.generate()
    pubkey_bytes = privkey.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return privkey, pubkey_bytes.hex()


def _sign(privkey: Ed25519PrivateKey, message: str) -> str:
    """Sign a message string, returning hex signature."""
    return privkey.sign(message.encode()).hex()


# ── Fixtures ──


@pytest.fixture
def mock_redis():
    """Mock Redis client that stores nonces in a dict."""
    store = {}
    redis = AsyncMock()

    async def _set(key, value, ex=None):
        store[key] = value

    async def _get(key):
        return store.get(key)

    async def _delete(key):
        if key in store:
            del store[key]
            return 1  # Redis DELETE returns count of deleted keys
        return 0

    redis.set = AsyncMock(side_effect=_set)
    redis.get = AsyncMock(side_effect=_get)
    redis.delete = AsyncMock(side_effect=_delete)
    redis.aclose = AsyncMock()

    return redis


@pytest.fixture
def mock_db():
    """Mock SQLAlchemy AsyncSession.

    Register endpoint does a SELECT then INSERT. We mock just enough
    to let the register flow complete.
    """
    db = AsyncMock()

    # For the SELECT query (checking existing identity)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    # For INSERT
    db.add = MagicMock()
    db.commit = AsyncMock()

    return db


@pytest.fixture
def app(mock_db):
    """FastAPI app with ZK auth router and mocked DB dependency."""
    from ndai.db.session import get_db

    app = FastAPI()
    app.include_router(zk_auth_router, prefix="/api/v1/zk-auth")

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ── Integration tests ──


class TestFullZKAuthFlow:
    """Full challenge-response authentication lifecycle."""

    def test_register_verify_flow(self, client, mock_redis):
        """Complete flow: register -> challenge -> sign -> verify -> JWT."""
        privkey, pubkey_hex = _generate_ed25519_keypair()

        # Step 1: Register
        register_message = f"NDAI_REGISTER:{pubkey_hex}"
        register_sig = _sign(privkey, register_message)

        resp = client.post("/api/v1/zk-auth/register", json={
            "public_key": pubkey_hex,
            "signature": register_sig,
            "alias": "shadowhunter",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "registered"

        # Step 2: Request challenge
        with patch("ndai.api.routers.zk_auth._get_redis", return_value=mock_redis):
            resp = client.post("/api/v1/zk-auth/challenge", json={
                "public_key": pubkey_hex,
            })
        assert resp.status_code == 200
        nonce = resp.json()["nonce"]
        assert len(nonce) == 64  # 32 bytes hex

        # Step 3: Sign the challenge
        auth_message = f"NDAI_AUTH:{nonce}"
        auth_sig = _sign(privkey, auth_message)

        # Step 4: Verify and get JWT
        with patch("ndai.api.routers.zk_auth._get_redis", return_value=mock_redis):
            resp = client.post("/api/v1/zk-auth/verify", json={
                "public_key": pubkey_hex,
                "nonce": nonce,
                "signature": auth_sig,
            })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        assert resp.json()["token_type"] == "bearer"

        # Step 5: Verify JWT contents
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == pubkey_hex
        assert payload["auth_type"] == "zk"
        assert "exp" in payload

    def test_register_with_invalid_signature_fails(self, client):
        """Register with wrong signature returns 401."""
        privkey, pubkey_hex = _generate_ed25519_keypair()

        # Sign a different message
        bad_sig = _sign(privkey, "not the register message")

        resp = client.post("/api/v1/zk-auth/register", json={
            "public_key": pubkey_hex,
            "signature": bad_sig,
        })
        assert resp.status_code == 401

    def test_verify_with_expired_nonce_fails(self, client):
        """Verify with a nonce that doesn't exist in Redis returns 401."""
        privkey, pubkey_hex = _generate_ed25519_keypair()

        # Create mock Redis that returns 0 for delete (nonce expired/missing)
        empty_redis = AsyncMock()
        empty_redis.delete = AsyncMock(return_value=0)
        empty_redis.aclose = AsyncMock()

        fake_nonce = "a1b2c3d4" * 8
        auth_message = f"NDAI_AUTH:{fake_nonce}"
        auth_sig = _sign(privkey, auth_message)

        with patch("ndai.api.routers.zk_auth._get_redis", return_value=empty_redis):
            resp = client.post("/api/v1/zk-auth/verify", json={
                "public_key": pubkey_hex,
                "nonce": fake_nonce,
                "signature": auth_sig,
            })
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()

    def test_verify_with_wrong_signature_fails(self, client, mock_redis):
        """Verify with incorrect signature returns 401."""
        privkey, pubkey_hex = _generate_ed25519_keypair()

        # Get a valid nonce first
        with patch("ndai.api.routers.zk_auth._get_redis", return_value=mock_redis):
            resp = client.post("/api/v1/zk-auth/challenge", json={
                "public_key": pubkey_hex,
            })
        nonce = resp.json()["nonce"]

        # Sign a different message (wrong signature)
        bad_sig = _sign(privkey, "totally wrong message")

        with patch("ndai.api.routers.zk_auth._get_redis", return_value=mock_redis):
            resp = client.post("/api/v1/zk-auth/verify", json={
                "public_key": pubkey_hex,
                "nonce": nonce,
                "signature": bad_sig,
            })
        assert resp.status_code == 401

    def test_nonce_is_one_time_use(self, client, mock_redis):
        """A nonce cannot be reused after successful verification."""
        privkey, pubkey_hex = _generate_ed25519_keypair()

        # Get nonce
        with patch("ndai.api.routers.zk_auth._get_redis", return_value=mock_redis):
            resp = client.post("/api/v1/zk-auth/challenge", json={
                "public_key": pubkey_hex,
            })
        nonce = resp.json()["nonce"]

        auth_message = f"NDAI_AUTH:{nonce}"
        auth_sig = _sign(privkey, auth_message)

        # First verify — should succeed
        with patch("ndai.api.routers.zk_auth._get_redis", return_value=mock_redis):
            resp = client.post("/api/v1/zk-auth/verify", json={
                "public_key": pubkey_hex,
                "nonce": nonce,
                "signature": auth_sig,
            })
        assert resp.status_code == 200

        # Second verify with same nonce — should fail (nonce deleted)
        with patch("ndai.api.routers.zk_auth._get_redis", return_value=mock_redis):
            resp = client.post("/api/v1/zk-auth/verify", json={
                "public_key": pubkey_hex,
                "nonce": nonce,
                "signature": auth_sig,
            })
        assert resp.status_code == 401


class TestTokenTypeEnforcement:
    """Verify that ZK-only endpoints reject regular tokens."""

    @pytest.mark.asyncio
    async def test_regular_jwt_rejected_by_get_zk_identity(self):
        """A standard JWT from create_access_token is rejected by get_zk_identity."""
        from ndai.api.dependencies import get_zk_identity
        from fastapi import HTTPException

        regular_token = create_access_token("user-123")

        class _FakeCredentials:
            def __init__(self, token):
                self.credentials = token
                self.scheme = "Bearer"

        with pytest.raises(HTTPException) as exc_info:
            await get_zk_identity(credentials=_FakeCredentials(regular_token))
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_zk_jwt_accepted_by_get_zk_identity(self):
        """A ZK JWT from create_zk_token is accepted by get_zk_identity."""
        from ndai.api.dependencies import get_zk_identity

        _, pubkey_hex = _generate_ed25519_keypair()
        zk_token = create_zk_token(pubkey_hex)

        class _FakeCredentials:
            def __init__(self, token):
                self.credentials = token
                self.scheme = "Bearer"

        result = await get_zk_identity(credentials=_FakeCredentials(zk_token))
        assert result == pubkey_hex

    def test_challenge_validates_pubkey_format(self, client):
        """Challenge endpoint rejects malformed public key hex."""
        resp = client.post("/api/v1/zk-auth/challenge", json={
            "public_key": "not-hex-and-wrong-length",
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_register_validates_pubkey_format(self, client):
        """Register endpoint rejects malformed public key hex."""
        resp = client.post("/api/v1/zk-auth/register", json={
            "public_key": "ZZZ",
            "signature": "aabb",
        })
        assert resp.status_code == 422
