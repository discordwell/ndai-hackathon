"""Invention management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.invention import (
    InventionCreateRequest,
    InventionResponse,
    ListingResponse,
)
from ndai.db.repositories import (
    create_invention,
    get_invention,
    list_active_inventions,
    list_inventions_by_seller,
)
from ndai.db.session import get_db

router = APIRouter()


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
    return InventionResponse(
        id=str(inv.id),
        title=inv.title,
        anonymized_summary=inv.anonymized_summary,
        category=inv.category,
        status=inv.status,
    )


@router.get("/", response_model=list[InventionResponse])
async def list_inventions(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inventions = await list_inventions_by_seller(db, uuid.UUID(user_id))
    return [
        InventionResponse(
            id=str(inv.id),
            title=inv.title,
            anonymized_summary=inv.anonymized_summary,
            category=inv.category,
            status=inv.status,
        )
        for inv in inventions
    ]


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
    return InventionResponse(
        id=str(inv.id),
        title=inv.title,
        anonymized_summary=inv.anonymized_summary,
        category=inv.category,
        status=inv.status,
    )
