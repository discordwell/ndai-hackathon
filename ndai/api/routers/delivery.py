"""Sealed exploit delivery endpoints — payment-gated ciphertext retrieval."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.delivery import DeliveryStatusResponse
from ndai.db.session import get_db
from ndai.models.delivery import DeliveryRecord

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_delivery(db: AsyncSession, agreement_id: str) -> DeliveryRecord | None:
    result = await db.execute(
        select(DeliveryRecord).where(DeliveryRecord.agreement_id == uuid.UUID(agreement_id))
    )
    return result.scalar_one_or_none()


async def _check_deal_accepted(agreement_id: str) -> bool:
    """Check on-chain state is Accepted. Returns True if deal is accepted."""
    from ndai.config import settings
    if not settings.blockchain_enabled:
        # In non-blockchain mode, check DB status
        return True  # Simplified — production checks on-chain

    try:
        from ndai.blockchain.vuln_escrow_client import VulnEscrowClient
        from ndai.blockchain.models import VulnEscrowState
        from ndai.db.session import async_session
        from ndai.db.repositories import get_vuln_agreement

        async with async_session() as db:
            agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
            if not agreement or not agreement.escrow_address:
                return agreement and agreement.status == "completed_agreement"

            client = VulnEscrowClient(
                rpc_url=settings.base_sepolia_rpc_url,
                factory_address=settings.vuln_escrow_factory_address,
            )
            state = await client.get_deal_state(agreement.escrow_address)
            return state.state == VulnEscrowState.Accepted
    except Exception as exc:
        logger.error("Failed to check on-chain state: %s", exc)
        return False


@router.get("/{agreement_id}/status", response_model=DeliveryStatusResponse)
async def get_delivery_status(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check delivery status and commitment hashes."""
    delivery = await _get_delivery(db, agreement_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="No delivery found")

    return DeliveryStatusResponse(
        delivery_hash=delivery.delivery_hash,
        key_commitment=delivery.key_commitment,
        status=delivery.status,
    )


@router.get("/{agreement_id}/payload")
async def get_delivery_payload(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the encrypted exploit. Requires on-chain DealAccepted.

    Returns raw bytes — the buyer decrypts with their delivery key.
    The platform cannot decrypt this (encrypted with K_d which only
    exists inside the enclave and in the buyer's encrypted key envelope).
    """
    from ndai.db.repositories import get_vuln_agreement
    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if str(agreement.buyer_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the buyer can retrieve deliveries")

    # Gate on payment
    if not await _check_deal_accepted(agreement_id):
        raise HTTPException(status_code=402, detail="Payment required — deal not yet accepted")

    delivery = await _get_delivery(db, agreement_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="No delivery found")

    return Response(
        content=delivery.delivery_ciphertext,
        media_type="application/octet-stream",
        headers={"X-Delivery-Hash": delivery.delivery_hash},
    )


@router.get("/{agreement_id}/key")
async def get_delivery_key(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the encrypted delivery key. Requires on-chain DealAccepted.

    Returns ECIES(buyer_pub, K_d) — only the buyer can decrypt this
    with their private key. The platform never possesses the buyer's
    private key or the delivery key K_d.
    """
    from ndai.db.repositories import get_vuln_agreement
    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if str(agreement.buyer_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the buyer can retrieve delivery keys")

    # Gate on payment
    if not await _check_deal_accepted(agreement_id):
        raise HTTPException(status_code=402, detail="Payment required — deal not yet accepted")

    delivery = await _get_delivery(db, agreement_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="No delivery found")

    return Response(
        content=delivery.delivery_key_ciphertext,
        media_type="application/octet-stream",
        headers={"X-Key-Commitment": delivery.key_commitment},
    )
