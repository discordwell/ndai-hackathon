"""Negotiation trigger and status endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.agreement import NegotiationOutcomeResponse
from ndai.config import settings
from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import SecurityParams
from ndai.enclave.session import NegotiationSession, SessionConfig

router = APIRouter()

# Store outcomes in memory for MVP
_outcomes: dict[str, dict] = {}


@router.post("/{agreement_id}/start", response_model=NegotiationOutcomeResponse)
async def start_negotiation(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    """Trigger a negotiation session for an agreement.

    In production, this launches a Nitro Enclave. For MVP, it runs
    the negotiation synchronously using the simulated TEE.
    """
    # For MVP, use hardcoded test data. In production, this would
    # look up the agreement and invention from the database.
    from ndai.api.routers.agreements import _agreements
    from ndai.api.routers.inventions import _inventions

    agreement = _agreements.get(agreement_id)
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

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

    config = SessionConfig(
        invention=invention,
        budget_cap=agreement.get("budget_cap", 1.0),
        security_params=SecurityParams(
            k=settings.shamir_k,
            p=settings.breach_detection_prob,
            c=settings.breach_penalty,
        ),
        max_rounds=settings.max_negotiation_rounds,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
    )

    session = NegotiationSession(config)
    result = session.run()

    _outcomes[agreement_id] = {
        "outcome": result.outcome.value,
        "final_price": result.final_price,
        "omega_hat": result.omega_hat,
        "negotiation_rounds": len(session.transcript.messages),
    }

    agreement["status"] = f"completed_{result.outcome.value}"

    return NegotiationOutcomeResponse(**_outcomes[agreement_id])


@router.get("/{agreement_id}/outcome", response_model=NegotiationOutcomeResponse)
async def get_outcome(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    outcome = _outcomes.get(agreement_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="No outcome yet")
    return NegotiationOutcomeResponse(**outcome)
