"""Agreement lifecycle endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.agreement import (
    AgreementCreateRequest,
    AgreementParamsRequest,
    AgreementResponse,
)
from ndai.db.repositories import (
    create_agreement,
    get_agreement,
    get_invention,
    list_agreements_for_user,
    update_agreement,
)
from ndai.db.session import get_db
from ndai.enclave.negotiation.engine import compute_theta
from ndai.services.audit import log_event

router = APIRouter()


def _agreement_response(a) -> AgreementResponse:
    return AgreementResponse(
        id=str(a.id),
        invention_id=str(a.invention_id),
        seller_id=str(a.seller_id),
        buyer_id=str(a.buyer_id),
        status=a.status,
        alpha_0=a.alpha_0,
        budget_cap=a.budget_cap,
        theta=a.theta,
        escrow_address=a.escrow_address,
        escrow_tx_hash=a.escrow_tx_hash,
    )


@router.post("/", response_model=AgreementResponse)
async def create_agreement_endpoint(
    request: AgreementCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Look up invention to get seller_id
    invention = await get_invention(db, uuid.UUID(request.invention_id))
    if not invention:
        raise HTTPException(status_code=404, detail="Invention not found")
    if str(invention.seller_id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot create agreement on your own invention")

    agreement = await create_agreement(
        db,
        invention_id=invention.id,
        seller_id=invention.seller_id,
        buyer_id=uuid.UUID(user_id),
        status="proposed",
        budget_cap=request.budget_cap,
    )
    await log_event(db, agreement.id, "agreement_created", uuid.UUID(user_id))
    return _agreement_response(agreement)


@router.get("/", response_model=list[AgreementResponse])
async def list_agreements(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreements = await list_agreements_for_user(db, uuid.UUID(user_id))
    return [_agreement_response(a) for a in agreements]


@router.get("/{agreement_id}", response_model=AgreementResponse)
async def get_agreement_endpoint(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")
    return _agreement_response(agreement)


@router.post("/{agreement_id}/params", response_model=AgreementResponse)
async def set_params(
    agreement_id: str,
    request: AgreementParamsRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    updates = {}
    if request.alpha_0 is not None:
        updates["alpha_0"] = request.alpha_0
        updates["theta"] = compute_theta(request.alpha_0)
    if request.budget_cap is not None:
        updates["budget_cap"] = request.budget_cap

    if updates:
        agreement = await update_agreement(db, agreement, **updates)
        await log_event(db, agreement.id, "params_set", uuid.UUID(user_id), updates)
    return _agreement_response(agreement)


@router.post("/{agreement_id}/confirm", response_model=AgreementResponse)
async def confirm_delegation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    agreement = await update_agreement(db, agreement, status="confirmed")
    await log_event(db, agreement.id, "delegation_confirmed", uuid.UUID(user_id))
    return _agreement_response(agreement)


@router.get("/{agreement_id}/escrow-state")
async def get_escrow_state(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get on-chain escrow state for an agreement."""
    from ndai.config import settings

    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")
    if not agreement.escrow_address:
        raise HTTPException(status_code=404, detail="No escrow for this agreement")

    if not settings.blockchain_enabled or not settings.base_sepolia_rpc_url:
        return {
            "escrow_address": agreement.escrow_address,
            "blockchain_unavailable": True,
        }

    try:
        from ndai.blockchain.escrow_client import EscrowClient
        client = EscrowClient(
            rpc_url=settings.base_sepolia_rpc_url,
            factory_address=settings.escrow_factory_address,
            chain_id=settings.chain_id,
        )
        state = await client.get_deal_state(agreement.escrow_address)
        return {
            "escrow_address": agreement.escrow_address,
            "state": state.state.name,
            "balance_wei": state.balance_wei,
            "reserve_price_wei": state.reserve_price_wei,
            "budget_cap_wei": state.budget_cap_wei,
            "final_price_wei": state.final_price_wei,
            "attestation_hash": "0x" + state.attestation_hash.hex(),
            "deadline": state.deadline,
        }
    except Exception as e:
        return {
            "escrow_address": agreement.escrow_address,
            "blockchain_unavailable": True,
            "error": str(e),
        }
