"""Badge system — ⚡ verified seller badges."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_zk_identity
from ndai.api.schemas.known_target import BadgePurchaseRequest, BadgeStatusResponse
from ndai.db.session import get_db
from ndai.models.zk_identity import VulnIdentity

router = APIRouter(prefix="", tags=["badges"])
logger = logging.getLogger(__name__)


@router.get("/me", response_model=BadgeStatusResponse)
async def get_my_badge(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Get badge status for the authenticated identity."""
    result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    return BadgeStatusResponse(
        has_badge=identity.has_badge,
        badge_type=identity.badge_type,
        badge_tx_hash=identity.badge_tx_hash,
        badge_awarded_at=identity.badge_awarded_at,
    )


@router.post("/purchase", response_model=BadgeStatusResponse)
async def purchase_badge(
    request: BadgePurchaseRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Register a badge purchase (after on-chain purchaseBadge() tx)."""
    result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    if identity.has_badge:
        raise HTTPException(status_code=400, detail="Already have a badge")

    # SECURITY TODO: Verify tx_hash on-chain via VerificationDepositClient.has_badge()
    # before granting the badge. Without this, anyone can submit a fake tx_hash
    # and get a badge for free, bypassing escrow on all future proposals.
    # Phase 2 must call: client.has_badge(request.eth_address) and verify it returns True.
    identity.has_badge = True
    identity.badge_type = "purchased"
    identity.badge_tx_hash = request.tx_hash
    identity.badge_awarded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(identity)

    logger.info("Badge purchased for %s (tx: %s)", pubkey[:16], request.tx_hash[:16])

    return BadgeStatusResponse(
        has_badge=identity.has_badge,
        badge_type=identity.badge_type,
        badge_tx_hash=identity.badge_tx_hash,
        badge_awarded_at=identity.badge_awarded_at,
    )


@router.get("/{pubkey_hex}", response_model=BadgeStatusResponse)
async def check_badge(
    pubkey_hex: str,
    _caller: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Check if a pubkey has a badge (public lookup)."""
    # Validate pubkey_hex is a valid 64-char hex string (Ed25519 public key)
    import re
    if not re.fullmatch(r"[0-9a-fA-F]{64}", pubkey_hex):
        raise HTTPException(status_code=400, detail="Invalid pubkey format — must be 64 hex characters")

    result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey_hex)
    )
    identity = result.scalar_one_or_none()
    if not identity:
        return BadgeStatusResponse(has_badge=False)

    return BadgeStatusResponse(
        has_badge=identity.has_badge,
        badge_type=identity.badge_type,
        badge_awarded_at=identity.badge_awarded_at,
    )
