"""Agreement lifecycle endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.agreement import (
    AgreementCreateRequest,
    AgreementParamsRequest,
    AgreementResponse,
)
from ndai.enclave.negotiation.engine import compute_theta

router = APIRouter()

# In-memory store for MVP
_agreements: dict[str, dict] = {}


@router.post("/", response_model=AgreementResponse)
async def create_agreement(
    request: AgreementCreateRequest,
    user_id: str = Depends(get_current_user),
):
    agreement_id = str(uuid.uuid4())
    _agreements[agreement_id] = {
        "id": agreement_id,
        "invention_id": request.invention_id,
        "seller_id": "",  # Would be looked up from invention
        "buyer_id": user_id,
        "status": "proposed",
        "alpha_0": None,
        "budget_cap": request.budget_cap,
        "theta": None,
    }
    return AgreementResponse(**_agreements[agreement_id])


@router.get("/", response_model=list[AgreementResponse])
async def list_agreements(user_id: str = Depends(get_current_user)):
    return [
        AgreementResponse(**a)
        for a in _agreements.values()
        if a["buyer_id"] == user_id or a["seller_id"] == user_id
    ]


@router.get("/{agreement_id}", response_model=AgreementResponse)
async def get_agreement(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    agreement = _agreements.get(agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Not found")
    if user_id not in (agreement["buyer_id"], agreement["seller_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")
    return AgreementResponse(**agreement)


@router.post("/{agreement_id}/params", response_model=AgreementResponse)
async def set_params(
    agreement_id: str,
    request: AgreementParamsRequest,
    user_id: str = Depends(get_current_user),
):
    agreement = _agreements.get(agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Not found")

    if request.alpha_0 is not None:
        agreement["alpha_0"] = request.alpha_0
        agreement["theta"] = compute_theta(request.alpha_0)
    if request.budget_cap is not None:
        agreement["budget_cap"] = request.budget_cap

    return AgreementResponse(**agreement)


@router.post("/{agreement_id}/confirm", response_model=AgreementResponse)
async def confirm_delegation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    agreement = _agreements.get(agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Not found")

    agreement["status"] = "confirmed"
    return AgreementResponse(**agreement)
