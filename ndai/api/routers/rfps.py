"""Buyer RFP (Request for Proposals) endpoints."""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.rfp import (
    RFPCreateRequest,
    RFPListingResponse,
    RFPProposalCreateRequest,
    RFPProposalResponse,
    RFPResponse,
    RFPUpdateRequest,
)
from ndai.db.repositories import (
    create_rfp,
    create_rfp_proposal,
    get_rfp,
    get_rfp_proposal,
    list_active_rfps,
    list_proposals_for_rfp,
    list_rfps_by_buyer,
    update_rfp,
    update_rfp_proposal,
)
from ndai.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


def _rfp_to_response(rfp) -> RFPResponse:
    return RFPResponse(
        id=str(rfp.id),
        buyer_id=str(rfp.buyer_id),
        title=rfp.title,
        target_software=rfp.target_software,
        target_version_range=rfp.target_version_range,
        desired_capability=rfp.desired_capability,
        threat_model=rfp.threat_model,
        target_environment=rfp.target_environment,
        acceptance_criteria=rfp.acceptance_criteria,
        has_patches=rfp.has_patches,
        budget_min_eth=rfp.budget_min_eth,
        budget_max_eth=rfp.budget_max_eth,
        deadline=rfp.deadline.isoformat() if rfp.deadline else "",
        exclusivity_preference=rfp.exclusivity_preference,
        status=rfp.status,
        created_at=rfp.created_at.isoformat() if rfp.created_at else "",
    )


def _rfp_to_listing(rfp) -> RFPListingResponse:
    return RFPListingResponse(
        id=str(rfp.id),
        title=rfp.title,
        target_software=rfp.target_software,
        target_version_range=rfp.target_version_range,
        desired_capability=rfp.desired_capability,
        has_patches=rfp.has_patches,
        budget_min_eth=rfp.budget_min_eth,
        budget_max_eth=rfp.budget_max_eth,
        deadline=rfp.deadline.isoformat() if rfp.deadline else "",
        exclusivity_preference=rfp.exclusivity_preference,
        status=rfp.status,
    )


def _proposal_to_response(p) -> RFPProposalResponse:
    return RFPProposalResponse(
        id=str(p.id),
        rfp_id=str(p.rfp_id),
        seller_id=str(p.seller_id),
        vulnerability_id=str(p.vulnerability_id) if p.vulnerability_id else None,
        message=p.message,
        proposed_price_eth=p.proposed_price_eth,
        estimated_delivery_days=p.estimated_delivery_days,
        status=p.status,
        created_at=p.created_at.isoformat() if p.created_at else "",
    )


# ── RFP CRUD ──

@router.post("/", response_model=RFPResponse, status_code=201)
async def create_rfp_endpoint(
    request: RFPCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buyer creates a new RFP."""
    if request.budget_min_eth > request.budget_max_eth:
        raise HTTPException(status_code=400, detail="budget_min_eth must be <= budget_max_eth")

    deadline = datetime.fromisoformat(request.deadline.replace("Z", "+00:00"))

    rfp = await create_rfp(
        db,
        buyer_id=uuid.UUID(user_id),
        title=request.title,
        target_software=request.target_software,
        target_version_range=request.target_version_range,
        desired_capability=request.desired_capability,
        threat_model=request.threat_model,
        target_environment=request.target_environment,
        acceptance_criteria=request.acceptance_criteria,
        budget_min_eth=request.budget_min_eth,
        budget_max_eth=request.budget_max_eth,
        deadline=deadline,
        exclusivity_preference=request.exclusivity_preference,
    )
    return _rfp_to_response(rfp)


@router.get("/", response_model=list[RFPResponse])
async def list_my_rfps(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's RFPs."""
    rfps = await list_rfps_by_buyer(db, uuid.UUID(user_id))
    return [_rfp_to_response(r) for r in rfps]


@router.get("/listings", response_model=list[RFPListingResponse])
async def list_rfp_listings(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active RFPs (seller-facing marketplace view)."""
    rfps = await list_active_rfps(db)
    return [_rfp_to_listing(r) for r in rfps]


@router.get("/{rfp_id}", response_model=RFPResponse)
async def get_rfp_endpoint(
    rfp_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get RFP detail."""
    rfp = await get_rfp(db, uuid.UUID(rfp_id))
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
    return _rfp_to_response(rfp)


@router.patch("/{rfp_id}", response_model=RFPResponse)
async def update_rfp_endpoint(
    rfp_id: str,
    request: RFPUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an RFP (owner only)."""
    rfp = await get_rfp(db, uuid.UUID(rfp_id))
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
    if str(rfp.buyer_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the RFP owner can update it")

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if "deadline" in updates:
        updates["deadline"] = datetime.fromisoformat(updates["deadline"].replace("Z", "+00:00"))
    if updates:
        rfp = await update_rfp(db, rfp, **updates)
    return _rfp_to_response(rfp)


@router.post("/{rfp_id}/cancel", response_model=RFPResponse)
async def cancel_rfp(
    rfp_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an RFP (owner only)."""
    rfp = await get_rfp(db, uuid.UUID(rfp_id))
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
    if str(rfp.buyer_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the RFP owner can cancel it")
    if rfp.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot cancel RFP in status: {rfp.status}")

    rfp = await update_rfp(db, rfp, status="cancelled")
    return _rfp_to_response(rfp)


# ── Patch Upload ──

@router.post("/{rfp_id}/upload-patches")
async def upload_patches(
    rfp_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload buyer overlay patches for an RFP."""
    rfp = await get_rfp(db, uuid.UUID(rfp_id))
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
    if str(rfp.buyer_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the RFP owner can upload patches")

    data = await file.read()
    max_size = 100 * 1024 * 1024  # 100 MB
    if len(data) > max_size:
        raise HTTPException(status_code=413, detail="Patch file too large (max 100MB)")

    patch_hash = hashlib.sha256(data).hexdigest()
    rfp = await update_rfp(db, rfp, has_patches=True, patch_data=data, patch_hash=patch_hash)
    return {"status": "ok", "size": len(data), "hash": patch_hash}


# ── Proposals ──

@router.post("/{rfp_id}/proposals", response_model=RFPProposalResponse, status_code=201)
async def submit_proposal(
    rfp_id: str,
    request: RFPProposalCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seller submits a proposal for an RFP."""
    rfp = await get_rfp(db, uuid.UUID(rfp_id))
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
    if rfp.status != "active":
        raise HTTPException(status_code=400, detail="RFP is not active")
    if str(rfp.buyer_id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot propose on your own RFP")

    proposal = await create_rfp_proposal(
        db,
        rfp_id=uuid.UUID(rfp_id),
        seller_id=uuid.UUID(user_id),
        vulnerability_id=uuid.UUID(request.vulnerability_id) if request.vulnerability_id else None,
        message=request.message,
        proposed_price_eth=request.proposed_price_eth,
        estimated_delivery_days=request.estimated_delivery_days,
    )
    return _proposal_to_response(proposal)


@router.get("/{rfp_id}/proposals", response_model=list[RFPProposalResponse])
async def list_proposals(
    rfp_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List proposals for an RFP."""
    rfp = await get_rfp(db, uuid.UUID(rfp_id))
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")

    proposals = await list_proposals_for_rfp(db, uuid.UUID(rfp_id))
    return [_proposal_to_response(p) for p in proposals]


@router.post("/proposals/{proposal_id}/accept", response_model=RFPProposalResponse)
async def accept_proposal(
    proposal_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buyer accepts a proposal, creating a VulnAgreement."""
    proposal = await get_rfp_proposal(db, uuid.UUID(proposal_id))
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    rfp = await get_rfp(db, proposal.rfp_id)
    if not rfp:
        raise HTTPException(status_code=404, detail="RFP not found")
    if str(rfp.buyer_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the RFP owner can accept proposals")
    if proposal.status != "pending":
        raise HTTPException(status_code=400, detail=f"Proposal is not pending: {proposal.status}")

    # Accept this proposal, reject others
    all_proposals = await list_proposals_for_rfp(db, rfp.id)
    for p in all_proposals:
        if p.id == proposal.id:
            await update_rfp_proposal(db, p, status="accepted")
        elif p.status == "pending":
            await update_rfp_proposal(db, p, status="rejected")

    # Mark RFP as fulfilled
    await update_rfp(db, rfp, status="fulfilled")

    # Refresh the accepted proposal
    proposal = await get_rfp_proposal(db, uuid.UUID(proposal_id))
    return _proposal_to_response(proposal)
