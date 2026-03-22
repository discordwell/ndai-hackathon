"""Negotiation trigger and status endpoints."""

import asyncio
import json
import logging
import traceback
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.agreement import NegotiationOutcomeResponse
from ndai.api.schemas.transparency import AuditLogEntry, TransparencyReport
from ndai.config import settings
from ndai.services.audit import get_audit_log, log_event
from ndai.db.repositories import (
    create_outcome,
    get_agreement,
    get_invention,
    get_outcome_by_agreement,
    update_agreement,
)
from ndai.db.session import async_session, get_db
from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import SecurityParams
from ndai.tee.orchestrator import EnclaveNegotiationConfig, EnclaveOrchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

# Transient per-process negotiation status (not persisted)
_statuses: dict[str, dict] = {}
# SSE progress queues per agreement_id
_progress_queues: dict[str, list[asyncio.Queue]] = {}
# Retain background task references to prevent GC cancellation
_tasks: set[asyncio.Task] = set()


def _get_provider():
    """Create the appropriate TEE provider based on settings.tee_mode."""
    if settings.tee_mode == "nitro":
        from ndai.tee.nitro_provider import NitroEnclaveProvider
        return NitroEnclaveProvider()
    elif settings.tee_mode == "dstack":
        from ndai.tee.dstack_provider import DstackProvider
        return DstackProvider()
    else:
        from ndai.tee.simulated_provider import SimulatedTEEProvider
        return SimulatedTEEProvider()


async def _run_negotiation_async(
    agreement_id: str,
    config: EnclaveNegotiationConfig,
) -> None:
    """Run negotiation via EnclaveOrchestrator (called as background task)."""
    try:
        _statuses[agreement_id] = {"status": "running"}
        await _emit_progress(agreement_id, "started", {})

        # Log negotiation start
        try:
            async with async_session() as db:
                await log_event(
                    db, uuid.UUID(agreement_id), "negotiation_started",
                    metadata={"llm_provider": config.llm_provider},
                )
        except Exception:
            logger.warning("Failed to log negotiation_started event")

        provider = _get_provider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=settings)
        result = await orchestrator.run_negotiation(config)

        # Handle blockchain-enriched result
        from ndai.tee.orchestrator import NegotiationOutcomeWithAttestation
        attestation_hash = None
        if isinstance(result, NegotiationOutcomeWithAttestation):
            attestation_hash = result.attestation_hash
            result = result.result  # unwrap to NegotiationResult

        # Submit outcome to on-chain escrow if blockchain enabled
        if settings.blockchain_enabled and attestation_hash and result.final_price is not None:
            try:
                from ndai.blockchain.escrow_client import EscrowClient
                escrow_client = EscrowClient(
                    rpc_url=settings.base_sepolia_rpc_url,
                    factory_address=settings.escrow_factory_address,
                    chain_id=settings.chain_id,
                )
                async with async_session() as db:
                    agreement = await get_agreement(db, uuid.UUID(agreement_id))
                    if agreement and agreement.escrow_address:
                        price_wei = int(result.final_price * 10**18)  # Convert to wei
                        tx_hash = await escrow_client.submit_outcome(
                            agreement.escrow_address,
                            price_wei,
                            attestation_hash,
                            settings.escrow_operator_key,
                        )
                        await update_agreement(db, agreement, escrow_tx_hash=tx_hash)
                        logger.info("Escrow outcome submitted: tx=%s", tx_hash)
            except Exception as e:
                logger.error("Failed to submit escrow outcome: %s", e)
                # Don't fail the negotiation over blockchain issues

        # Persist outcome to DB
        async with async_session() as db:
            await create_outcome(
                db,
                agreement_id=uuid.UUID(agreement_id),
                outcome=result.outcome.value,
                final_price=result.final_price,
                negotiation_rounds=result.negotiation_rounds,
                error_details=result.reason if result.outcome.value == "error" else None,
            )
            agreement = await get_agreement(db, uuid.UUID(agreement_id))
            if agreement:
                await update_agreement(
                    db, agreement, status=f"completed_{result.outcome.value}"
                )

        outcome_data = {
            "outcome": result.outcome.value,
            "final_price": result.final_price,
            "reason": result.reason or None,
            "negotiation_rounds": result.negotiation_rounds,
            "omega_hat": result.omega_hat,
        }
        _statuses[agreement_id] = {
            "status": "completed",
            "outcome": outcome_data,
        }
        # Log completion
        try:
            async with async_session() as db:
                await log_event(
                    db, uuid.UUID(agreement_id), "negotiation_completed",
                    metadata={"outcome": result.outcome.value, "rounds": result.negotiation_rounds},
                )
        except Exception:
            logger.warning("Failed to log negotiation_completed event")

        # Notify SSE subscribers
        await _emit_progress(agreement_id, "complete", outcome_data)
    except Exception:
        logger.error("Negotiation failed for %s: %s", agreement_id, traceback.format_exc())
        _statuses[agreement_id] = {
            "status": "error",
            "error": "Negotiation failed. Check server logs for details.",
        }
        # Update agreement status in DB
        try:
            async with async_session() as db:
                agreement = await get_agreement(db, uuid.UUID(agreement_id))
                if agreement:
                    await update_agreement(db, agreement, status="completed_error")
        except Exception:
            logger.error("Failed to update agreement status after error")


@router.post("/{agreement_id}/start")
async def start_negotiation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a negotiation session for an agreement.

    Returns 202 with status polling URL. The negotiation runs in a
    background task using the EnclaveOrchestrator.
    """
    # Prevent double-start
    if agreement_id in _statuses and _statuses[agreement_id]["status"] in ("pending", "running"):
        return {"status": _statuses[agreement_id]["status"]}

    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    invention = await get_invention(db, agreement.invention_id)
    if not invention:
        raise HTTPException(status_code=404, detail="Invention not found")

    invention_sub = InventionSubmission(
        title=invention.title,
        full_description=invention.full_description or "",
        technical_domain=invention.technical_domain or "",
        novelty_claims=invention.novelty_claims or [],
        prior_art_known=invention.prior_art_known or [],
        potential_applications=invention.potential_applications or [],
        development_stage=invention.development_stage or "concept",
        self_assessed_value=invention.self_assessed_value or 0.5,
        outside_option_value=invention.outside_option_value or 0.3,
        confidential_sections=invention.confidential_sections or [],
        max_disclosure_fraction=invention.max_disclosure_fraction or 1.0,
    )

    # Resolve LLM provider settings
    if settings.llm_provider == "openai":
        _api_key = settings.openai_api_key
        _llm_model = settings.openai_model
    else:
        _api_key = settings.anthropic_api_key
        _llm_model = settings.anthropic_model

    config = EnclaveNegotiationConfig(
        invention=invention_sub,
        budget_cap=agreement.budget_cap or 1.0,
        security_params=SecurityParams(
            k=settings.shamir_k,
            p=settings.breach_detection_prob,
            c=settings.breach_penalty,
        ),
        max_rounds=settings.max_negotiation_rounds,
        llm_provider=settings.llm_provider,
        api_key=_api_key,
        llm_model=_llm_model,
        blockchain_enabled=settings.blockchain_enabled,
    )

    _statuses[agreement_id] = {"status": "pending"}

    # Run in background task using the orchestrator
    task = asyncio.create_task(
        _run_negotiation_async(agreement_id, config)
    )
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return {"status": "pending"}


@router.get("/{agreement_id}/status")
async def get_status(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll negotiation status."""
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if agreement and user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check in-memory status first (for active negotiations)
    status = _statuses.get(agreement_id)
    if status:
        return status

    # Fall back to DB outcome
    outcome = await get_outcome_by_agreement(db, uuid.UUID(agreement_id))
    if outcome:
        return {
            "status": "completed",
            "outcome": {
                "outcome": outcome.outcome,
                "final_price": outcome.final_price,
                "reason": outcome.error_details,
            },
        }

    raise HTTPException(status_code=404, detail="No negotiation started")


@router.get("/{agreement_id}/outcome", response_model=NegotiationOutcomeResponse)
async def get_outcome(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if agreement and user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check in-memory first
    mem_status = _statuses.get(agreement_id)
    if mem_status and mem_status.get("outcome"):
        mem_outcome = mem_status["outcome"]
        return NegotiationOutcomeResponse(
            outcome=mem_outcome.get("outcome"),
            final_price=mem_outcome.get("final_price"),
            reason=mem_outcome.get("reason"),
            negotiation_rounds=mem_outcome.get("negotiation_rounds"),
            omega_hat=mem_outcome.get("omega_hat"),
        )

    # Fall back to DB
    outcome = await get_outcome_by_agreement(db, uuid.UUID(agreement_id))
    if not outcome:
        raise HTTPException(status_code=404, detail="No outcome yet")
    return NegotiationOutcomeResponse(
        outcome=outcome.outcome,
        final_price=outcome.final_price,
        reason=outcome.error_details,
        negotiation_rounds=outcome.negotiation_rounds,
        omega_hat=outcome.omega_hat,
    )


async def _emit_progress(agreement_id: str, phase: str, data: dict | None = None):
    """Send a progress event to all SSE subscribers for an agreement."""
    queues = _progress_queues.get(agreement_id, [])
    event = {"phase": phase, "data": data or {}}
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


@router.get("/{agreement_id}/stream")
async def stream_negotiation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for real-time negotiation progress."""
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
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
                    # Send keepalive
                    yield ": keepalive\n\n"
        finally:
            _progress_queues.get(agreement_id, []).remove(queue) if queue in _progress_queues.get(agreement_id, []) else None

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{agreement_id}/transparency", response_model=TransparencyReport)
async def get_transparency_report(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a verifiable transparency report for a completed negotiation."""
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    outcome = await get_outcome_by_agreement(db, uuid.UUID(agreement_id))
    if not outcome:
        raise HTTPException(status_code=404, detail="No outcome yet")

    return TransparencyReport(
        agreement_id=agreement_id,
        outcome=outcome.outcome,
        final_price=outcome.final_price,
        transcript_hash=outcome.transcript_key_ref,
        negotiation_rounds=outcome.negotiation_rounds,
        timestamp=outcome.created_at.isoformat() if outcome.created_at else None,
        verification_steps=[
            "1. Verify enclave attestation (COSE Sign1 + AWS root CA)",
            "2. Verify transcript hash chain integrity",
            "3. Verify final hash signature with enclave public key",
            "4. Compare outcome against deterministic Nash baseline",
        ],
    )


@router.get("/{agreement_id}/audit-log", response_model=list[AuditLogEntry])
async def get_audit_log_endpoint(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log entries for an agreement."""
    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")

    entries = await get_audit_log(db, uuid.UUID(agreement_id))
    return [
        AuditLogEntry(
            id=e.id,
            agreement_id=str(e.agreement_id) if e.agreement_id else None,
            event_type=e.event_type,
            actor_id=str(e.actor_id) if e.actor_id else None,
            metadata=e.metadata_,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in entries
    ]
