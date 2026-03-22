"""Tests for ZK authentication — token creation, identity extraction, Ed25519 verification."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ndai:ndai@localhost:5432/ndai")

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from jose import jwt

from ndai.api.dependencies import (
    create_access_token,
    create_zk_token,
    get_current_user,
    get_zk_identity,
)
from ndai.api.routers.zk_auth import _verify_ed25519
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


class _FakeCredentials:
    """Minimal stand-in for HTTPAuthorizationCredentials."""

    def __init__(self, token: str):
        self.credentials = token
        self.scheme = "Bearer"


# ── Tests ──


class TestCreateZKToken:
    def test_zk_token_has_auth_type(self):
        """create_zk_token produces a JWT with auth_type='zk'."""
        privkey, pubkey_hex = _generate_ed25519_keypair()
        token = create_zk_token(pubkey_hex)

        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["auth_type"] == "zk"
        assert payload["sub"] == pubkey_hex


class TestGetZKIdentity:
    @pytest.mark.asyncio
    async def test_get_zk_identity_accepts_zk_token(self):
        """get_zk_identity successfully extracts pubkey from a ZK JWT."""
        privkey, pubkey_hex = _generate_ed25519_keypair()
        token = create_zk_token(pubkey_hex)

        result = await get_zk_identity(credentials=_FakeCredentials(token))
        assert result == pubkey_hex

    @pytest.mark.asyncio
    async def test_get_zk_identity_rejects_regular_token(self):
        """get_zk_identity rejects a standard JWT (no auth_type='zk')."""
        token = create_access_token("user-123")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_zk_identity(credentials=_FakeCredentials(token))
        assert exc_info.value.status_code == 401


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_get_current_user_accepts_regular_token(self):
        """get_current_user works with standard JWTs."""
        token = create_access_token("user-456")

        result = await get_current_user(credentials=_FakeCredentials(token))
        assert result == "user-456"

    @pytest.mark.asyncio
    async def test_get_current_user_also_accepts_zk_token(self):
        """get_current_user does not reject ZK tokens — it only checks 'sub'."""
        privkey, pubkey_hex = _generate_ed25519_keypair()
        token = create_zk_token(pubkey_hex)

        result = await get_current_user(credentials=_FakeCredentials(token))
        assert result == pubkey_hex


class TestEd25519Verification:
    def test_ed25519_signature_verification(self):
        """Valid Ed25519 signature passes _verify_ed25519."""
        privkey, pubkey_hex = _generate_ed25519_keypair()
        message = "NDAI_REGISTER:" + pubkey_hex
        sig_hex = _sign(privkey, message)

        # Should not raise
        _verify_ed25519(pubkey_hex, sig_hex, message)

    def test_invalid_signature_rejected(self):
        """Bad signature raises HTTPException 401."""
        privkey, pubkey_hex = _generate_ed25519_keypair()
        message = "NDAI_REGISTER:" + pubkey_hex

        # Sign a different message so the signature won't verify
        wrong_sig_hex = _sign(privkey, "wrong message")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _verify_ed25519(pubkey_hex, wrong_sig_hex, message)
        assert exc_info.value.status_code == 401

    def test_invalid_pubkey_rejected(self):
        """Malformed public key hex raises HTTPException (caught as 401)."""
        from fastapi import HTTPException

        # 63 chars (odd-length hex) — invalid
        bad_pubkey = "abcdef" * 10 + "abc"  # 63 chars

        with pytest.raises((HTTPException, Exception)):
            _verify_ed25519(bad_pubkey, "aa" * 64, "test")

    def test_wrong_key_signature_mismatch(self):
        """Signature from key A does not verify against key B."""
        privkey_a, pubkey_a_hex = _generate_ed25519_keypair()
        _privkey_b, pubkey_b_hex = _generate_ed25519_keypair()

        message = "NDAI_AUTH:some-nonce"
        sig_hex = _sign(privkey_a, message)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _verify_ed25519(pubkey_b_hex, sig_hex, message)
        assert exc_info.value.status_code == 401
