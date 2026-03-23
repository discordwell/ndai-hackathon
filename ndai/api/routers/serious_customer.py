"""Serious Customer deposit and status endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_zk_identity
from ndai.api.schemas.zk_auction import (
    MinDepositResponse,
    SeriousCustomerDepositRequest,
    SeriousCustomerStatusResponse,
)
from ndai.db.session import get_db
from ndai.models.zk_identity import VulnIdentity

router = APIRouter(prefix="", tags=["serious-customer"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=SeriousCustomerStatusResponse)
async def get_sc_status(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Return Serious Customer status for the authenticated identity."""
    result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    return SeriousCustomerStatusResponse(
        is_serious_customer=identity.is_serious_customer,
        sc_type=identity.sc_type,
        sc_deposit_eth=identity.sc_deposit_eth,
        sc_eth_address=identity.sc_eth_address,
        sc_awarded_at=identity.sc_awarded_at,
        sc_refunded=identity.sc_refunded,
    )


@router.post("/deposit", response_model=SeriousCustomerStatusResponse, status_code=201)
async def register_sc_deposit(
    request: SeriousCustomerDepositRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Register a Serious Customer deposit (after on-chain deposit() tx)."""
    result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
    )
    identity = result.scalar_one_or_none()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")

    if identity.is_serious_customer:
        raise HTTPException(status_code=409, detail="Already a Serious Customer")

    identity.is_serious_customer = True
    identity.sc_type = "deposited"
    identity.sc_deposit_tx_hash = request.tx_hash
    identity.sc_deposit_eth = request.deposit_eth
    identity.sc_eth_address = request.eth_address
    identity.sc_awarded_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(identity)

    return SeriousCustomerStatusResponse(
        is_serious_customer=True,
        sc_type="deposited",
        sc_deposit_eth=identity.sc_deposit_eth,
        sc_eth_address=identity.sc_eth_address,
        sc_awarded_at=identity.sc_awarded_at,
        sc_refunded=False,
    )


@router.get("/min-deposit", response_model=MinDepositResponse)
async def get_min_deposit():
    """Return the current minimum deposit in ETH (from on-chain Chainlink price).

    Falls back to a static estimate if blockchain is not enabled.
    """
    from ndai.config import settings

    if settings.serious_customer_address and settings.base_sepolia_rpc_url:
        try:
            from ndai.blockchain.serious_customer_client import SeriousCustomerClient

            client = SeriousCustomerClient(
                settings.base_sepolia_rpc_url,
                settings.serious_customer_address,
                settings.chain_id,
            )
            min_wei = await client.get_min_deposit_wei()
            price = await client.get_latest_price()
            return MinDepositResponse(
                min_deposit_eth=min_wei / 1e18,
                eth_price_usd=price / 1e8,
            )
        except Exception:
            logger.exception("Failed to read on-chain min deposit")

    # Fallback: $5,000 at ~$2,500/ETH = 2 ETH
    return MinDepositResponse(min_deposit_eth=2.0, eth_price_usd=2500.0)
