"""Vulnerability marketplace endpoints — submission, listing, agreements, negotiation."""

import asyncio
import json
import logging
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.vulnerability import (
    VulnAgreementCreateRequest,
    VulnAgreementResponse,
    VulnCreateRequest,
    VulnListingResponse,
    VulnOutcomeResponse,
    VulnResponse,
)
from ndai.config import settings
from ndai.db.repositories import (
    create_vuln_agreement,
    create_vuln_outcome,
    create_vulnerability,
    get_vulnerability,
    get_vuln_agreement,
    get_vuln_outcome_by_agreement,
    list_active_vulnerabilities,
    list_vuln_agreements_for_user,
    list_vulnerabilities_by_seller,
    update_vuln_agreement,
)
from ndai.db.session import async_session, get_db
from ndai.enclave.agents.base_agent import VulnerabilitySubmission
from ndai.enclave.vuln_session import VulnNegotiationSession, VulnSessionConfig

router = APIRouter()
logger = logging.getLogger(__name__)

# Transient per-process status (not persisted)
_statuses: dict[str, dict] = {}
_progress_queues: dict[str, list[asyncio.Queue]] = {}
_tasks: set[asyncio.Task] = set()


# ── Vulnerability CRUD ──

@router.post("/", response_model=VulnResponse, status_code=201)
async def create_vuln_endpoint(
    request: VulnCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vuln = await create_vulnerability(
        db,
        seller_id=uuid.UUID(user_id),
        **request.model_dump(),
    )
    return VulnResponse(
        id=str(vuln.id),
        target_software=vuln.target_software,
        target_version=vuln.target_version,
        vulnerability_class=vuln.vulnerability_class,
        impact_type=vuln.impact_type,
        cvss_self_assessed=vuln.cvss_self_assessed,
        patch_status=vuln.patch_status,
        exclusivity=vuln.exclusivity,
        status=vuln.status,
    )


@router.get("/", response_model=list[VulnResponse])
async def list_vulns(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vulns = await list_vulnerabilities_by_seller(db, uuid.UUID(user_id))
    return [
        VulnResponse(
            id=str(v.id),
            target_software=v.target_software,
            target_version=v.target_version,
            vulnerability_class=v.vulnerability_class,
            impact_type=v.impact_type,
            cvss_self_assessed=v.cvss_self_assessed,
            patch_status=v.patch_status,
            exclusivity=v.exclusivity,
            status=v.status,
        )
        for v in vulns
    ]


@router.get("/listings", response_model=list[VulnListingResponse])
async def list_vuln_listings(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Buyer-facing anonymized listings. Requires auth — zero-day metadata is sensitive."""
    vulns = await list_active_vulnerabilities(db)
    return [
        VulnListingResponse(
            id=str(v.id),
            target_software=v.target_software,
            vulnerability_class=v.vulnerability_class,
            impact_type=v.impact_type,
            patch_status=v.patch_status,
            exclusivity=v.exclusivity,
            anonymized_summary=v.anonymized_summary,
            cvss_self_assessed=v.cvss_self_assessed,
        )
        for v in vulns
    ]


@router.get("/{vuln_id}", response_model=VulnResponse)
async def get_vuln_endpoint(
    vuln_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vuln = await get_vulnerability(db, uuid.UUID(vuln_id))
    if not vuln or str(vuln.seller_id) != user_id:
        raise HTTPException(status_code=404, detail="Not found")
    return VulnResponse(
        id=str(vuln.id),
        target_software=vuln.target_software,
        target_version=vuln.target_version,
        vulnerability_class=vuln.vulnerability_class,
        impact_type=vuln.impact_type,
        cvss_self_assessed=vuln.cvss_self_assessed,
        patch_status=vuln.patch_status,
        exclusivity=vuln.exclusivity,
        status=vuln.status,
    )


# ── Agreements ──

@router.post("/agreements", response_model=VulnAgreementResponse, status_code=201)
async def create_vuln_agreement_endpoint(
    request: VulnAgreementCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vuln = await get_vulnerability(db, uuid.UUID(request.vulnerability_id))
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    if str(vuln.seller_id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot buy your own vulnerability")

    agreement = await create_vuln_agreement(
        db,
        vulnerability_id=vuln.id,
        seller_id=vuln.seller_id,
        buyer_id=uuid.UUID(user_id),
        alpha_0=vuln.outside_option_value,
        budget_cap=request.budget_cap,
    )
    return VulnAgreementResponse(
        id=str(agreement.id),
        vulnerability_id=str(agreement.vulnerability_id),
        seller_id=str(agreement.seller_id),
        buyer_id=str(agreement.buyer_id),
        status=agreement.status,
        alpha_0=agreement.alpha_0,
        budget_cap=agreement.budget_cap,
    )


@router.get("/agreements", response_model=list[VulnAgreementResponse])
async def list_vuln_agreements(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreements = await list_vuln_agreements_for_user(db, uuid.UUID(user_id))
    return [
        VulnAgreementResponse(
            id=str(a.id),
            vulnerability_id=str(a.vulnerability_id),
            seller_id=str(a.seller_id),
            buyer_id=str(a.buyer_id),
            status=a.status,
            alpha_0=a.alpha_0,
            budget_cap=a.budget_cap,
        )
        for a in agreements
    ]


@router.get("/agreements/{agreement_id}", response_model=VulnAgreementResponse)
async def get_vuln_agreement_endpoint(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")
    return VulnAgreementResponse(
        id=str(agreement.id),
        vulnerability_id=str(agreement.vulnerability_id),
        seller_id=str(agreement.seller_id),
        buyer_id=str(agreement.buyer_id),
        status=agreement.status,
        alpha_0=agreement.alpha_0,
        budget_cap=agreement.budget_cap,
    )


# ── Negotiation ──

async def _run_vuln_negotiation_async(
    agreement_id: str,
    config: VulnSessionConfig,
) -> None:
    """Run vulnerability negotiation as background task."""
    try:
        _statuses[agreement_id] = {"status": "running"}
        await _emit_progress(agreement_id, "started", {})

        session = VulnNegotiationSession(config)
        timeout = settings.negotiation_timeout_sec

        result = await asyncio.wait_for(
            asyncio.to_thread(session.run),
            timeout=timeout,
        )

        # Persist outcome
        async with async_session() as db:
            await create_vuln_outcome(
                db,
                agreement_id=uuid.UUID(agreement_id),
                outcome=result.outcome.value,
                final_price=result.final_price,
                disclosure_level=result.disclosure_level,
                current_value_at_settlement=result.current_value,
                negotiation_rounds=result.negotiation_rounds,
                error_details=result.reason if result.outcome.value == "error" else None,
            )
            agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
            if agreement:
                await update_vuln_agreement(
                    db, agreement, status=f"completed_{result.outcome.value}"
                )

        outcome_data = {
            "outcome": result.outcome.value,
            "final_price": result.final_price,
            "disclosure_level": result.disclosure_level,
            "reason": result.reason or None,
            "negotiation_rounds": result.negotiation_rounds,
        }
        _statuses[agreement_id] = {"status": "completed", "outcome": outcome_data}
        await _emit_progress(agreement_id, "complete", outcome_data)

    except Exception:
        logger.error("Vuln negotiation failed for %s: %s", agreement_id, traceback.format_exc())
        _statuses[agreement_id] = {
            "status": "error",
            "error": "Negotiation failed. Check server logs.",
        }
        try:
            async with async_session() as db:
                agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
                if agreement:
                    await update_vuln_agreement(db, agreement, status="completed_error")
        except Exception:
            logger.error("Failed to update vuln agreement status after error")


@router.post("/negotiations/{agreement_id}/start")
async def start_vuln_negotiation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a vulnerability negotiation session."""
    if agreement_id in _statuses and _statuses[agreement_id]["status"] in ("pending", "running"):
        return {"status": _statuses[agreement_id]["status"]}

    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    vuln = await get_vulnerability(db, agreement.vulnerability_id)
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    vuln_sub = VulnerabilitySubmission(
        target_software=vuln.target_software,
        target_version=vuln.target_version,
        vulnerability_class=vuln.vulnerability_class,
        impact_type=vuln.impact_type,
        affected_component=vuln.affected_component or "",
        cvss_self_assessed=vuln.cvss_self_assessed,
        discovery_date=vuln.discovery_date,
        patch_status=vuln.patch_status or "unpatched",
        exclusivity=vuln.exclusivity or "exclusive",
        outside_option_value=vuln.outside_option_value or 0.3,
        max_disclosure_level=vuln.max_disclosure_level or 3,
        embargo_days=vuln.embargo_days or 90,
        software_category=vuln.software_category or "default",
    )

    if settings.llm_provider == "openai":
        _api_key = settings.openai_api_key
        _llm_model = settings.openai_model
    else:
        _api_key = settings.anthropic_api_key
        _llm_model = settings.anthropic_model

    config = VulnSessionConfig(
        vulnerability=vuln_sub,
        budget_cap=agreement.budget_cap or 1.0,
        max_rounds=settings.max_negotiation_rounds,
        llm_provider=settings.llm_provider,
        api_key=_api_key,
        llm_model=_llm_model,
        software_category=vuln.software_category or "default",
    )

    _statuses[agreement_id] = {"status": "pending"}

    task = asyncio.create_task(_run_vuln_negotiation_async(agreement_id, config))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return {"status": "pending"}


@router.get("/negotiations/{agreement_id}/status")
async def get_vuln_negotiation_status(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if agreement and user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    status = _statuses.get(agreement_id)
    if status:
        return status

    outcome = await get_vuln_outcome_by_agreement(db, uuid.UUID(agreement_id))
    if outcome:
        return {
            "status": "completed",
            "outcome": {
                "outcome": outcome.outcome,
                "final_price": outcome.final_price,
                "disclosure_level": outcome.disclosure_level,
                "reason": outcome.error_details,
            },
        }

    raise HTTPException(status_code=404, detail="No negotiation started")


@router.get("/negotiations/{agreement_id}/outcome", response_model=VulnOutcomeResponse)
async def get_vuln_outcome(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if agreement and user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    mem_status = _statuses.get(agreement_id)
    if mem_status and mem_status.get("outcome"):
        return VulnOutcomeResponse(**mem_status["outcome"])

    outcome = await get_vuln_outcome_by_agreement(db, uuid.UUID(agreement_id))
    if not outcome:
        raise HTTPException(status_code=404, detail="No outcome yet")
    return VulnOutcomeResponse(
        outcome=outcome.outcome,
        final_price=outcome.final_price,
        disclosure_level=outcome.disclosure_level,
        reason=outcome.error_details,
        negotiation_rounds=outcome.negotiation_rounds,
    )


async def _emit_progress(agreement_id: str, phase: str, data: dict | None = None):
    queues = _progress_queues.get(agreement_id, [])
    event = {"phase": phase, "data": data or {}}
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


@router.get("/negotiations/{agreement_id}/stream")
async def stream_vuln_negotiation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for real-time vulnerability negotiation progress."""
    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if agreement and user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    if agreement_id not in _progress_queues:
        _progress_queues[agreement_id] = []
    _progress_queues[agreement_id].append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['phase']}\ndata: {json.dumps(event['data'])}\n\n"
                    if event["phase"] == "complete":
                        break
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in _progress_queues.get(agreement_id, []):
                _progress_queues[agreement_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
