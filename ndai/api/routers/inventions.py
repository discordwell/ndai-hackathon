"""Invention management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.invention import (
    InventionCreateRequest,
    InventionResponse,
    InventionUpdateRequest,
    ListingResponse,
)
from ndai.db.repositories import (
    create_invention,
    get_invention,
    list_active_inventions,
    list_inventions_by_seller,
    update_invention,
)
from ndai.db.session import get_db

router = APIRouter()


def _to_response(inv) -> InventionResponse:
    return InventionResponse(
        id=str(inv.id),
        title=inv.title,
        anonymized_summary=inv.anonymized_summary,
        category=inv.category,
        status=inv.status,
        full_description=inv.full_description,
        technical_domain=inv.technical_domain,
        development_stage=inv.development_stage,
        self_assessed_value=inv.self_assessed_value,
        outside_option_value=inv.outside_option_value,
        novelty_claims=inv.novelty_claims,
        prior_art_known=inv.prior_art_known,
        potential_applications=inv.potential_applications,
        confidential_sections=inv.confidential_sections,
        max_disclosure_fraction=inv.max_disclosure_fraction,
        created_at=inv.created_at.isoformat() if inv.created_at else None,
    )


@router.post("/", response_model=InventionResponse)
async def create_invention_endpoint(
    request: InventionCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inv = await create_invention(
        db,
        seller_id=uuid.UUID(user_id),
        status="active",
        **request.model_dump(),
    )
    return _to_response(inv)


@router.get("/", response_model=list[InventionResponse])
async def list_inventions(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    limit = min(limit, 200)
    inventions = await list_inventions_by_seller(db, uuid.UUID(user_id), limit=limit, offset=offset)
    return [_to_response(inv) for inv in inventions]


@router.get("/listings", response_model=list[ListingResponse])
async def list_public_listings(db: AsyncSession = Depends(get_db)):
    """Buyer-facing anonymized listings."""
    inventions = await list_active_inventions(db)
    return [
        ListingResponse(
            id=str(inv.id),
            title=inv.title,
            anonymized_summary=inv.anonymized_summary,
            category=inv.category,
            development_stage=inv.development_stage or "unknown",
        )
        for inv in inventions
    ]


@router.get("/{invention_id}", response_model=InventionResponse)
async def get_invention_endpoint(
    invention_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inv = await get_invention(db, uuid.UUID(invention_id))
    if not inv or str(inv.seller_id) != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    return _to_response(inv)


@router.put("/{invention_id}", response_model=InventionResponse)
async def update_invention_endpoint(
    invention_id: str,
    request: InventionUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inv = await get_invention(db, uuid.UUID(invention_id))
    if not inv or str(inv.seller_id) != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    if inv.status != "active":
        raise HTTPException(status_code=400, detail="Cannot edit invention that is not active")
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    inv = await update_invention(db, inv, **updates)
    return _to_response(inv)


@router.delete("/{invention_id}")
async def delete_invention_endpoint(
    invention_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inv = await get_invention(db, uuid.UUID(invention_id))
    if not inv or str(inv.seller_id) != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    if inv.status != "active":
        raise HTTPException(status_code=400, detail="Cannot withdraw invention that is not active")
    await update_invention(db, inv, status="withdrawn")
    return {"status": "withdrawn"}
