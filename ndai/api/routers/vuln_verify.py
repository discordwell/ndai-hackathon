"""Vulnerability verification endpoints — target specs, EIF builds, PoC verification."""

import asyncio
import base64
import hashlib
import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.vuln_verify import (
    EIFManifestResponse,
    OverlayUploadRequest,
    TargetSpecCreateRequest,
    TargetSpecResponse,
    VerificationResultResponse,
)
from ndai.config import settings
from ndai.db.session import async_session, get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory state for async builds and verifications
_build_statuses: dict[str, dict] = {}
_verify_statuses: dict[str, dict] = {}
_pending_overlays: dict[str, bytes] = {}  # agreement_id -> encrypted overlay
_tasks: set[asyncio.Task] = set()


@router.post("/target-specs", response_model=TargetSpecResponse, status_code=201)
async def create_target_spec(
    request: TargetSpecCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seller submits a target specification for their vulnerability."""
    from ndai.db.repositories import get_vulnerability
    from ndai.models.vuln_verify import TargetSpecRecord

    vuln = await get_vulnerability(db, uuid.UUID(request.vulnerability_id))
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    if str(vuln.seller_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the seller can submit target specs")

    poc_hash = hashlib.sha256(request.poc.script_content.encode()).hexdigest()

    record = TargetSpecRecord(
        id=uuid.uuid4(),
        vulnerability_id=vuln.id,
        base_image=request.base_image,
        packages=[p.model_dump() for p in request.packages],
        config_files=[c.model_dump() for c in request.config_files],
        services=[s.model_dump() for s in request.services],
        poc_hash=poc_hash,
        expected_outcome=request.expected_outcome.model_dump(),
        status="pending",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return TargetSpecResponse(
        id=str(record.id),
        vulnerability_id=str(record.vulnerability_id),
        base_image=record.base_image,
        package_count=len(request.packages),
        status=record.status,
    )


@router.get("/target-specs/{spec_id}", response_model=TargetSpecResponse)
async def get_target_spec(
    spec_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from ndai.models.vuln_verify import TargetSpecRecord

    result = await db.execute(
        select(TargetSpecRecord).where(TargetSpecRecord.id == uuid.UUID(spec_id))
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Target spec not found")

    # Check in-memory build status
    status = record.status
    if spec_id in _build_statuses:
        status = _build_statuses[spec_id].get("status", status)

    return TargetSpecResponse(
        id=str(record.id),
        vulnerability_id=str(record.vulnerability_id),
        base_image=record.base_image,
        package_count=len(record.packages) if record.packages else 0,
        status=status,
    )


@router.post("/target-specs/{spec_id}/build")
async def trigger_eif_build(
    spec_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an async EIF build for a target spec."""
    from sqlalchemy import select
    from ndai.models.vuln_verify import TargetSpecRecord

    if spec_id in _build_statuses and _build_statuses[spec_id].get("status") == "building":
        return {"status": "building"}

    result = await db.execute(
        select(TargetSpecRecord).where(TargetSpecRecord.id == uuid.UUID(spec_id))
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Target spec not found")

    _build_statuses[spec_id] = {"status": "building"}

    async def _build():
        try:
            from ndai.enclave.vuln_verify.builder import EIFBuilder
            from ndai.enclave.vuln_verify.models import (
                ConfigFile, ExpectedOutcome, PinnedPackage, PoCSpec, ServiceSpec, TargetSpec,
            )

            spec = TargetSpec(
                spec_id=spec_id,
                base_image=record.base_image,
                packages=[PinnedPackage(**p) for p in record.packages],
                config_files=[ConfigFile(**c) for c in (record.config_files or [])],
                services=[ServiceSpec(**s) for s in (record.services or [])],
                poc=PoCSpec(script_type="bash", script_content="true"),  # PoC not needed for build
                expected_outcome=ExpectedOutcome(**(record.expected_outcome or {})),
            )

            builder = EIFBuilder(
                build_dir=settings.vuln_eif_build_dir,
                eif_store_dir=settings.vuln_eif_store_dir,
            )
            manifest = await builder.build_eif(spec)

            # Persist manifest
            from ndai.models.vuln_verify import EIFManifestRecord
            async with async_session() as db2:
                manifest_record = EIFManifestRecord(
                    id=uuid.uuid4(),
                    spec_id=uuid.UUID(spec_id),
                    eif_path=manifest.eif_path,
                    pcr0=manifest.pcr0,
                    pcr1=manifest.pcr1,
                    pcr2=manifest.pcr2,
                    docker_image_hash=manifest.docker_image_hash,
                )
                db2.add(manifest_record)
                await db2.commit()

            _build_statuses[spec_id] = {
                "status": "built",
                "pcr0": manifest.pcr0,
                "pcr1": manifest.pcr1,
                "pcr2": manifest.pcr2,
            }
        except Exception:
            logger.error("EIF build failed: %s", traceback.format_exc())
            _build_statuses[spec_id] = {"status": "failed", "error": "Build failed"}

    task = asyncio.create_task(_build())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return {"status": "building"}


@router.get("/target-specs/{spec_id}/manifest", response_model=EIFManifestResponse)
async def get_manifest(
    spec_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from ndai.models.vuln_verify import EIFManifestRecord

    result = await db.execute(
        select(EIFManifestRecord).where(EIFManifestRecord.spec_id == uuid.UUID(spec_id))
    )
    record = result.scalar_one_or_none()
    if not record:
        # Check in-memory
        if spec_id in _build_statuses:
            bs = _build_statuses[spec_id]
            return EIFManifestResponse(
                spec_id=spec_id,
                pcr0=bs.get("pcr0", ""),
                pcr1=bs.get("pcr1", ""),
                pcr2=bs.get("pcr2", ""),
                status=bs.get("status", "unknown"),
                built_at=None,
            )
        raise HTTPException(status_code=404, detail="No manifest found")

    return EIFManifestResponse(
        spec_id=str(record.spec_id),
        pcr0=record.pcr0,
        pcr1=record.pcr1,
        pcr2=record.pcr2,
        status="built",
        built_at=record.built_at.isoformat() if record.built_at else None,
    )


@router.post("/{agreement_id}/overlay")
async def upload_overlay(
    agreement_id: str,
    request: OverlayUploadRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buyer uploads an encrypted overlay for PoC verification."""
    from ndai.db.repositories import get_vuln_agreement

    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if str(agreement.buyer_id) != user_id:
        raise HTTPException(status_code=403, detail="Only the buyer can upload overlays")

    encrypted_bytes = base64.b64decode(request.encrypted_overlay)
    max_size = settings.vuln_overlay_max_size_mb * 1024 * 1024
    if len(encrypted_bytes) > max_size:
        raise HTTPException(status_code=413, detail="Overlay too large")

    _pending_overlays[agreement_id] = encrypted_bytes
    return {"status": "ok", "size": len(encrypted_bytes)}


@router.post("/{agreement_id}/verify")
async def start_verification(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger PoC verification for an agreement."""
    if agreement_id in _verify_statuses and _verify_statuses[agreement_id].get("status") in ("pending", "running"):
        return {"status": _verify_statuses[agreement_id]["status"]}

    from ndai.db.repositories import get_vuln_agreement, get_vulnerability
    from sqlalchemy import select
    from ndai.models.vuln_verify import TargetSpecRecord

    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Find target spec for this vulnerability
    result = await db.execute(
        select(TargetSpecRecord)
        .where(TargetSpecRecord.vulnerability_id == agreement.vulnerability_id)
        .order_by(TargetSpecRecord.created_at.desc())
    )
    spec_record = result.scalars().first()
    if not spec_record:
        raise HTTPException(status_code=404, detail="No target spec found for this vulnerability")

    _verify_statuses[agreement_id] = {"status": "pending"}

    async def _verify():
        try:
            _verify_statuses[agreement_id] = {"status": "running"}

            from ndai.enclave.vuln_verify.models import (
                ConfigFile, ExpectedOutcome, PinnedPackage, PoCSpec, ServiceSpec, TargetSpec,
            )
            from ndai.tee.vuln_verify_orchestrator import VulnVerifyOrchestrator, VerificationConfig

            spec = TargetSpec(
                spec_id=str(spec_record.id),
                base_image=spec_record.base_image,
                packages=[PinnedPackage(**p) for p in spec_record.packages],
                config_files=[ConfigFile(**c) for c in (spec_record.config_files or [])],
                services=[ServiceSpec(**s) for s in (spec_record.services or [])],
                poc=PoCSpec(script_type="bash", script_content="true"),  # TODO: store PoC properly
                expected_outcome=ExpectedOutcome(**(spec_record.expected_outcome or {})),
            )

            overlay_encrypted = _pending_overlays.pop(agreement_id, None)

            # Get provider
            if settings.tee_mode == "nitro":
                from ndai.tee.nitro_provider import NitroEnclaveProvider
                provider = NitroEnclaveProvider()
            else:
                from ndai.tee.simulated_provider import SimulatedTEEProvider
                provider = SimulatedTEEProvider()

            orchestrator = VulnVerifyOrchestrator(provider=provider, settings=settings)
            config = VerificationConfig(
                target_spec=spec,
                buyer_overlay_encrypted=overlay_encrypted,
            )
            outcome = await orchestrator.run_verification(config)

            # Persist result
            from ndai.models.vuln_verify import VerificationResultRecord
            async with async_session() as db2:
                vr = VerificationResultRecord(
                    id=uuid.uuid4(),
                    spec_id=uuid.UUID(str(spec_record.id)),
                    agreement_id=uuid.UUID(agreement_id),
                    buyer_id=agreement.buyer_id,
                    unpatched_matches=outcome.unpatched_matches,
                    patched_matches=outcome.patched_matches,
                    overlap_detected=outcome.overlap_detected,
                    verification_chain_hash=outcome.verification_chain_hash,
                    attestation_pcr0=outcome.pcr0,
                )
                db2.add(vr)
                await db2.commit()

            _verify_statuses[agreement_id] = {
                "status": "completed",
                "result": {
                    "unpatched_matches": outcome.unpatched_matches,
                    "patched_matches": outcome.patched_matches,
                    "overlap_detected": outcome.overlap_detected,
                    "verification_chain_hash": outcome.verification_chain_hash,
                    "pcr0": outcome.pcr0,
                },
            }
        except Exception:
            logger.error("Verification failed: %s", traceback.format_exc())
            _verify_statuses[agreement_id] = {"status": "error", "error": "Verification failed"}

    task = asyncio.create_task(_verify())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return {"status": "pending"}


@router.get("/{agreement_id}/result", response_model=VerificationResultResponse)
async def get_verification_result(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check in-memory first
    status = _verify_statuses.get(agreement_id)
    if status and status.get("result"):
        return VerificationResultResponse(**status["result"])

    # Fall back to DB
    from sqlalchemy import select
    from ndai.models.vuln_verify import VerificationResultRecord

    result = await db.execute(
        select(VerificationResultRecord)
        .where(VerificationResultRecord.agreement_id == uuid.UUID(agreement_id))
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="No verification result yet")

    return VerificationResultResponse(
        unpatched_matches=record.unpatched_matches,
        patched_matches=record.patched_matches,
        overlap_detected=record.overlap_detected,
        verification_chain_hash=record.verification_chain_hash,
        pcr0=record.attestation_pcr0,
    )
