"""Bounty endpoints for buyer-initiated 0day requests."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_zk_identity
from ndai.api.schemas.bounty import (
    BountyCreateRequest,
    BountyListingResponse,
    BountyRespondRequest,
    BountyResponse,
)
from ndai.api.schemas.zk_vulnerability import ZKVulnAgreementResponse
from ndai.db.session import get_db
from ndai.models.bounty import Bounty
from ndai.models.zk_vulnerability import ZKVulnAgreement, ZKVulnerability

router = APIRouter(prefix="", tags=["bounties"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=BountyResponse, status_code=201)
async def create_bounty(
    request: BountyCreateRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Create a bounty request for a specific vulnerability type."""
    bounty = Bounty(
        requester_pubkey=pubkey,
        **request.model_dump(),
    )
    db.add(bounty)
    await db.commit()
    await db.refresh(bounty)
    return _bounty_to_response(bounty)


@router.get("/", response_model=list[BountyListingResponse])
async def list_open_bounties(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List all open bounties (marketplace browsing)."""
    result = await db.execute(
        select(Bounty).where(Bounty.status == "open")
    )
    bounties = result.scalars().all()
    return [_bounty_to_listing(b) for b in bounties]


@router.get("/mine", response_model=list[BountyResponse])
async def list_my_bounties(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List bounties created by the authenticated identity."""
    result = await db.execute(
        select(Bounty).where(Bounty.requester_pubkey == pubkey)
    )
    bounties = result.scalars().all()
    return [_bounty_to_response(b) for b in bounties]


@router.get("/{bounty_id}", response_model=BountyResponse)
async def get_bounty(
    bounty_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Get bounty detail."""
    bounty = await _get_bounty_or_404(db, bounty_id)
    return _bounty_to_response(bounty)


@router.post("/{bounty_id}/respond", response_model=ZKVulnAgreementResponse, status_code=201)
async def respond_to_bounty(
    bounty_id: str,
    request: BountyRespondRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Seller responds to a bounty by submitting a matching vulnerability.

    Creates a ZKVulnerability + ZKVulnAgreement linking the bounty requester as buyer.
    """
    bounty = await _get_bounty_or_404(db, bounty_id)

    if bounty.status != "open":
        raise HTTPException(status_code=400, detail="Bounty is not open")
    if bounty.requester_pubkey == pubkey:
        raise HTTPException(status_code=400, detail="Cannot respond to your own bounty")

    # Create the vulnerability
    vuln = ZKVulnerability(
        seller_pubkey=pubkey,
        target_software=request.target_software,
        target_version=request.target_version,
        vulnerability_class=request.vulnerability_class,
        impact_type=request.impact_type,
        affected_component=request.affected_component,
        anonymized_summary=request.anonymized_summary,
        cvss_self_assessed=request.cvss_self_assessed,
        asking_price_eth=request.asking_price_eth,
        discovery_date=request.discovery_date,
    )
    db.add(vuln)
    await db.flush()  # Get vuln.id without committing

    # Create the agreement linking seller (responder) to buyer (bounty requester)
    agreement = ZKVulnAgreement(
        vulnerability_id=vuln.id,
        seller_pubkey=pubkey,
        buyer_pubkey=bounty.requester_pubkey,
    )
    db.add(agreement)

    # Mark bounty as fulfilled
    bounty.status = "fulfilled"

    await db.commit()
    await db.refresh(agreement)

    return ZKVulnAgreementResponse(
        id=str(agreement.id),
        vulnerability_id=str(agreement.vulnerability_id),
        seller_pubkey=agreement.seller_pubkey,
        buyer_pubkey=agreement.buyer_pubkey,
        status=agreement.status,
        escrow_address=agreement.escrow_address,
        seller_eth_address=agreement.seller_eth_address,
        buyer_eth_address=agreement.buyer_eth_address,
        created_at=agreement.created_at,
    )


@router.delete("/{bounty_id}", status_code=204)
async def cancel_bounty(
    bounty_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a bounty (only the owner can cancel)."""
    bounty = await _get_bounty_or_404(db, bounty_id)

    if bounty.requester_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Not authorized")
    if bounty.status != "open":
        raise HTTPException(status_code=400, detail="Bounty is not open")

    bounty.status = "cancelled"
    await db.commit()


# ── Helpers ──


async def _get_bounty_or_404(db: AsyncSession, bounty_id: str) -> Bounty:
    result = await db.execute(
        select(Bounty).where(Bounty.id == uuid.UUID(bounty_id))
    )
    bounty = result.scalar_one_or_none()
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")
    return bounty


def _bounty_to_response(b: Bounty) -> BountyResponse:
    return BountyResponse(
        id=str(b.id),
        requester_pubkey=b.requester_pubkey,
        target_software=b.target_software,
        target_version_constraint=b.target_version_constraint,
        desired_impact=b.desired_impact,
        desired_vulnerability_class=b.desired_vulnerability_class,
        budget_eth=b.budget_eth,
        description=b.description,
        deadline=b.deadline,
        status=b.status,
        created_at=b.created_at,
    )


def _bounty_to_listing(b: Bounty) -> BountyListingResponse:
    return BountyListingResponse(
        id=str(b.id),
        requester_pubkey=b.requester_pubkey,
        target_software=b.target_software,
        target_version_constraint=b.target_version_constraint,
        desired_impact=b.desired_impact,
        desired_vulnerability_class=b.desired_vulnerability_class,
        budget_eth=b.budget_eth,
        description=b.description,
        deadline=b.deadline,
        status=b.status,
        created_at=b.created_at,
    )
