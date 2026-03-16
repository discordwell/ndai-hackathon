"""Negotiation trigger and status endpoints."""

import asyncio
import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.agreement import NegotiationOutcomeResponse
from ndai.config import settings
from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import SecurityParams
from ndai.tee.orchestrator import EnclaveNegotiationConfig, EnclaveOrchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

# Store outcomes and status in memory for MVP
_outcomes: dict[str, dict] = {}
_statuses: dict[str, dict] = {}


def _get_provider():
    """Create the appropriate TEE provider based on settings.tee_mode."""
    if settings.tee_mode == "nitro":
        from ndai.tee.nitro_provider import NitroEnclaveProvider
        return NitroEnclaveProvider()
    else:
        from ndai.tee.simulated_provider import SimulatedTEEProvider
        return SimulatedTEEProvider()


async def _run_negotiation_async(
    agreement_id: str,
    config: EnclaveNegotiationConfig,
    agreement: dict,
) -> None:
    """Run negotiation via EnclaveOrchestrator (called as background task)."""
    try:
        _statuses[agreement_id] = {"status": "running"}

        provider = _get_provider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=settings)
        result = await orchestrator.run_negotiation(config)

        _outcomes[agreement_id] = {
            "outcome": result.outcome.value,
            "final_price": result.final_price,
            "reason": result.reason or None,
        }
        agreement["status"] = f"completed_{result.outcome.value}"
        _statuses[agreement_id] = {
            "status": "completed",
            "outcome": _outcomes[agreement_id],
        }
    except Exception:
        logger.error("Negotiation failed for %s: %s", agreement_id, traceback.format_exc())
        _statuses[agreement_id] = {
            "status": "error",
            "error": "Negotiation failed. Check server logs for details.",
        }
        agreement["status"] = "completed_error"


@router.post("/{agreement_id}/start")
async def start_negotiation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    """Trigger a negotiation session for an agreement.

    Returns 202 with status polling URL. The negotiation runs in a
    background task using the EnclaveOrchestrator.
    """
    from ndai.api.routers.agreements import _agreements
    from ndai.api.routers.inventions import _inventions

    # Prevent double-start
    if agreement_id in _statuses and _statuses[agreement_id]["status"] in ("pending", "running"):
        return {"status": _statuses[agreement_id]["status"]}

    agreement = _agreements.get(agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (agreement["buyer_id"], agreement["seller_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")

    invention_data = _inventions.get(agreement["invention_id"])
    if not invention_data:
        raise HTTPException(status_code=404, detail="Invention not found")

    invention = InventionSubmission(
        title=invention_data["title"],
        full_description=invention_data.get("full_description", ""),
        technical_domain=invention_data.get("technical_domain", ""),
        novelty_claims=invention_data.get("novelty_claims", []),
        prior_art_known=invention_data.get("prior_art_known", []),
        potential_applications=invention_data.get("potential_applications", []),
        development_stage=invention_data.get("development_stage", "concept"),
        self_assessed_value=invention_data.get("self_assessed_value", 0.5),
        outside_option_value=invention_data.get("outside_option_value", 0.3),
        confidential_sections=invention_data.get("confidential_sections", []),
        max_disclosure_fraction=invention_data.get("max_disclosure_fraction", 1.0),
    )

    # Resolve LLM provider settings
    if settings.llm_provider == "openai":
        _api_key = settings.openai_api_key
        _llm_model = settings.openai_model
    else:
        _api_key = settings.anthropic_api_key
        _llm_model = settings.anthropic_model

    config = EnclaveNegotiationConfig(
        invention=invention,
        budget_cap=agreement.get("budget_cap", 1.0),
        security_params=SecurityParams(
            k=settings.shamir_k,
            p=settings.breach_detection_prob,
            c=settings.breach_penalty,
        ),
        max_rounds=settings.max_negotiation_rounds,
        llm_provider=settings.llm_provider,
        api_key=_api_key,
        llm_model=_llm_model,
    )

    _statuses[agreement_id] = {"status": "pending"}

    # Run in background task using the orchestrator
    asyncio.create_task(
        _run_negotiation_async(agreement_id, config, agreement)
    )

    return {"status": "pending"}


@router.get("/{agreement_id}/status")
async def get_status(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    """Poll negotiation status."""
    from ndai.api.routers.agreements import _agreements

    agreement = _agreements.get(agreement_id)
    if agreement and user_id not in (agreement["buyer_id"], agreement["seller_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")

    status = _statuses.get(agreement_id)
    if not status:
        raise HTTPException(status_code=404, detail="No negotiation started")
    return status


@router.get("/{agreement_id}/outcome", response_model=NegotiationOutcomeResponse)
async def get_outcome(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    from ndai.api.routers.agreements import _agreements

    agreement = _agreements.get(agreement_id)
    if agreement and user_id not in (agreement["buyer_id"], agreement["seller_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")

    outcome = _outcomes.get(agreement_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="No outcome yet")
    return NegotiationOutcomeResponse(**outcome)
