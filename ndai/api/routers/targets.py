"""Known verification targets catalog — browse available 0day targets."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_zk_identity
from ndai.api.schemas.known_target import (
    KnownTargetDetailResponse,
    KnownTargetResponse,
    TargetBuildResponse,
)
from ndai.db.session import get_db
from ndai.models.known_target import KnownTarget, TargetBuild

router = APIRouter(prefix="", tags=["targets"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[KnownTargetResponse])
async def list_targets(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List all active verification targets."""
    result = await db.execute(
        select(KnownTarget).where(KnownTarget.is_active.is_(True)).order_by(KnownTarget.slug)
    )
    targets = result.scalars().all()

    # Check for pre-built EIFs
    target_ids = [t.id for t in targets]
    builds_result = await db.execute(
        select(TargetBuild).where(
            TargetBuild.target_id.in_(target_ids),
            TargetBuild.status == "ready",
        )
    )
    ready_targets = {b.target_id for b in builds_result.scalars().all()}

    return [
        KnownTargetResponse(
            id=str(t.id),
            slug=t.slug,
            display_name=t.display_name,
            platform=t.platform,
            current_version=t.current_version,
            verification_method=t.verification_method,
            poc_script_type=t.poc_script_type,
            poc_instructions=t.poc_instructions,
            escrow_amount_usd=t.escrow_amount_usd,
            icon_emoji=t.icon_emoji,
            is_active=t.is_active,
            has_prebuilt=t.id in ready_targets,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in targets
    ]


@router.get("/{target_id}", response_model=KnownTargetDetailResponse)
async def get_target(
    target_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Get target detail with build status and PoC instructions."""
    import uuid as _uuid

    result = await db.execute(
        select(KnownTarget).where(KnownTarget.id == _uuid.UUID(target_id))
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    # Latest build
    build_result = await db.execute(
        select(TargetBuild)
        .where(TargetBuild.target_id == target.id)
        .order_by(TargetBuild.built_at.desc())
        .limit(1)
    )
    latest_build = build_result.scalar_one_or_none()

    return KnownTargetDetailResponse(
        id=str(target.id),
        slug=target.slug,
        display_name=target.display_name,
        platform=target.platform,
        current_version=target.current_version,
        verification_method=target.verification_method,
        poc_script_type=target.poc_script_type,
        poc_instructions=target.poc_instructions,
        escrow_amount_usd=target.escrow_amount_usd,
        icon_emoji=target.icon_emoji,
        is_active=target.is_active,
        has_prebuilt=latest_build is not None and latest_build.status == "ready",
        base_image=target.base_image,
        service_user=target.service_user,
        platform_config_json=target.platform_config_json,
        build_status=latest_build.status if latest_build else None,
        build_version=latest_build.version if latest_build else None,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


@router.get("/{target_id}/builds", response_model=list[TargetBuildResponse])
async def list_target_builds(
    target_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List builds for a target."""
    import uuid as _uuid

    result = await db.execute(
        select(TargetBuild)
        .where(TargetBuild.target_id == _uuid.UUID(target_id))
        .order_by(TargetBuild.built_at.desc())
        .limit(20)
    )
    builds = result.scalars().all()
    return [
        TargetBuildResponse(
            id=str(b.id),
            version=b.version,
            build_type=b.build_type,
            cache_key=b.cache_key,
            status=b.status,
            pcr0=b.pcr0,
            built_at=b.built_at,
        )
        for b in builds
    ]
