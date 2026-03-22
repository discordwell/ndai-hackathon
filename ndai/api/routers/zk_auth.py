"""Zero-knowledge authentication endpoints using Ed25519 signatures."""

import os

import redis.asyncio as aioredis
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import create_zk_token
from ndai.api.schemas.zk_auth import (
    ZKChallengeRequest,
    ZKChallengeResponse,
    ZKRegisterRequest,
    ZKRegisterResponse,
    ZKVerifyRequest,
    ZKVerifyResponse,
)
from ndai.config import settings
from ndai.db.session import get_db
from ndai.models.zk_identity import VulnIdentity

router = APIRouter(prefix="", tags=["zk-auth"])


async def _get_redis() -> aioredis.Redis:
    """Get a Redis client from settings."""
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _verify_ed25519(public_key_hex: str, signature_hex: str, message: str) -> None:
    """Verify an Ed25519 signature; raises HTTPException on failure."""
    try:
        pubkey_obj = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pubkey_obj.verify(bytes.fromhex(signature_hex), message.encode())
    except (InvalidSignature, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )


@router.post("/register", response_model=ZKRegisterResponse)
async def register(request: ZKRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a ZK identity. Verify Ed25519 signature of 'NDAI_REGISTER:{public_key}'."""
    message = f"NDAI_REGISTER:{request.public_key}"
    _verify_ed25519(request.public_key, request.signature, message)

    # Check if identity already exists
    result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == request.public_key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update alias if provided
        if request.alias is not None:
            existing.alias = request.alias
            await db.commit()
        return ZKRegisterResponse(status="already_registered")

    identity = VulnIdentity(public_key=request.public_key, alias=request.alias)
    db.add(identity)
    await db.commit()
    return ZKRegisterResponse(status="registered")


@router.post("/challenge", response_model=ZKChallengeResponse)
async def challenge(request: ZKChallengeRequest):
    """Generate a one-time nonce challenge for ZK authentication."""
    nonce = os.urandom(32).hex()

    redis_client = await _get_redis()
    try:
        redis_key = f"zk_challenge:{request.public_key}:{nonce}"
        await redis_client.set(redis_key, "1", ex=60)  # 60-second TTL
    finally:
        await redis_client.aclose()

    return ZKChallengeResponse(nonce=nonce)


@router.post("/verify", response_model=ZKVerifyResponse)
async def verify(request: ZKVerifyRequest):
    """Verify a signed nonce challenge and return a JWT."""
    # Verify Ed25519 signature FIRST (before consuming the nonce, so a bad
    # signature doesn't waste the user's challenge)
    message = f"NDAI_AUTH:{request.nonce}"
    _verify_ed25519(request.public_key, request.signature, message)

    # Atomically consume the nonce — redis DELETE returns the number of keys
    # removed, so if two concurrent requests race, only one gets deleted=1.
    redis_client = await _get_redis()
    try:
        redis_key = f"zk_challenge:{request.public_key}:{request.nonce}"
        deleted = await redis_client.delete(redis_key)
        if deleted == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired nonce",
            )
    finally:
        await redis_client.aclose()

    # Issue JWT
    token = create_zk_token(request.public_key)
    return ZKVerifyResponse(access_token=token)
