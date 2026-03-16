"""Invention management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.invention import (
    InventionCreateRequest,
    InventionResponse,
    ListingResponse,
)

router = APIRouter()

# In-memory store for MVP
_inventions: dict[str, dict] = {}


@router.post("/", response_model=InventionResponse)
async def create_invention(
    request: InventionCreateRequest,
    user_id: str = Depends(get_current_user),
):
    invention_id = str(uuid.uuid4())
    _inventions[invention_id] = {
        "id": invention_id,
        "seller_id": user_id,
        "status": "active",
        **request.model_dump(),
    }
    return InventionResponse(
        id=invention_id,
        title=request.title,
        anonymized_summary=request.anonymized_summary,
        category=request.category,
        status="active",
    )


@router.get("/", response_model=list[InventionResponse])
async def list_inventions(user_id: str = Depends(get_current_user)):
    return [
        InventionResponse(
            id=inv["id"],
            title=inv["title"],
            anonymized_summary=inv.get("anonymized_summary"),
            category=inv.get("category"),
            status=inv["status"],
        )
        for inv in _inventions.values()
        if inv["seller_id"] == user_id
    ]


@router.get("/listings", response_model=list[ListingResponse])
async def list_public_listings():
    """Buyer-facing anonymized listings."""
    return [
        ListingResponse(
            id=inv["id"],
            title=inv["title"],
            anonymized_summary=inv.get("anonymized_summary"),
            category=inv.get("category"),
            development_stage=inv.get("development_stage", "unknown"),
        )
        for inv in _inventions.values()
        if inv["status"] == "active"
    ]


@router.get("/{invention_id}", response_model=InventionResponse)
async def get_invention(
    invention_id: str,
    user_id: str = Depends(get_current_user),
):
    inv = _inventions.get(invention_id)
    if not inv or inv["seller_id"] != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    return InventionResponse(
        id=inv["id"],
        title=inv["title"],
        anonymized_summary=inv.get("anonymized_summary"),
        category=inv.get("category"),
        status=inv["status"],
    )
