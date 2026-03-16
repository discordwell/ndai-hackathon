"""NDAI negotiation session orchestrator.

Runs inside the TEE (or simulated TEE). Wires together:
- Seller agent (disclosure + offer evaluation)
- Buyer agent (invention evaluation + pricing)
- Negotiation engine (Nash bargaining, constraints)
- Protocol state machine (round management)
"""

import logging
from dataclasses import dataclass, field

from ndai.enclave.agents.base_agent import AgentMessage, InventionSubmission
from ndai.enclave.agents.buyer_agent import BuyerAgent
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.agents.seller_agent import SellerAgent
from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    NegotiationParams,
    NegotiationResult,
    SecurityParams,
    check_budget_cap,
    check_deal_viability,
    compute_bilateral_price,
    compute_seller_payoff,
    compute_theta,
    resolve_negotiation,  # unilateral baseline for audit comparison
    security_capacity,
)

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Configuration for a negotiation session."""

    invention: InventionSubmission
    budget_cap: float
    security_params: SecurityParams
    max_rounds: int = 5
    llm_provider: str = "anthropic"  # "anthropic" or "openai"
    api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    # Legacy aliases (kept for backwards compatibility)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"


@dataclass
class SessionTranscript:
    """Full record of a negotiation session."""

    messages: list[AgentMessage] = field(default_factory=list)
    result: NegotiationResult | None = None
    deterministic_result: NegotiationResult | None = None


class NegotiationSession:
    """Orchestrates a complete NDAI negotiation.

    Flow:
    1. Compute security parameters (Phi, theta)
    2. Seller agent decides disclosure (omega_hat) — 1 API call
    3. Buyer agent evaluates (v_b) — 1 API call
    4. Bilateral Nash bargaining: P* = (v_b + alpha_0 * omega_hat) / 2
    """

    def __init__(self, config: SessionConfig, progress_callback=None):
        self.config = config
        self.phi = security_capacity(config.security_params)
        self.theta = compute_theta(config.invention.outside_option_value)
        self.transcript = SessionTranscript()
        self._progress_callback = progress_callback

        # Resolve API key and model: prefer generic fields, fall back to legacy
        api_key = config.api_key or config.anthropic_api_key
        llm_model = config.llm_model
        # If llm_model is still the default and legacy anthropic_model was changed, use it
        if config.llm_model == "claude-sonnet-4-20250514" and config.anthropic_model != "claude-sonnet-4-20250514":
            llm_model = config.anthropic_model

        if config.llm_provider == "openai":
            from ndai.enclave.agents.openai_llm_client import OpenAILLMClient
            llm = OpenAILLMClient(api_key=api_key, model=llm_model)
        else:
            llm = LLMClient(api_key=api_key, model=llm_model)

        self.seller_agent = SellerAgent(
            invention=config.invention,
            llm_client=llm,
            security_threshold=self.phi,
        )
        self.buyer_agent = BuyerAgent(
            budget_cap=config.budget_cap,
            theta=self.theta,
            llm_client=llm,
        )

    def run(self) -> NegotiationResult:
        """Execute the full negotiation protocol.

        Flow:
        1. Seller disclosure (omega_hat)
        2. Buyer evaluation (v_b)
        3. If max_rounds > 1 and deal is viable: multi-round offer/counter loop
        4. Final bilateral Nash resolution as backstop

        Returns the final NegotiationResult.
        """
        # Always compute the deterministic (unilateral) result for audit comparison
        self.transcript.deterministic_result = resolve_negotiation(
            NegotiationParams(
                omega=self.config.invention.self_assessed_value,
                alpha_0=self.config.invention.outside_option_value,
                budget_cap=self.config.budget_cap,
                security_params=self.config.security_params,
            )
        )

        omega = self.config.invention.self_assessed_value
        alpha_0 = self.config.invention.outside_option_value

        # Phase 1: Seller disclosure → omega_hat (1 API call)
        logger.info("Phase 1: Seller agent deciding disclosure")
        self._emit_progress("seller_disclosure", {})
        disclosure_msg = self.seller_agent.decide_disclosure()
        self.transcript.messages.append(disclosure_msg)

        if not disclosure_msg.disclosure:
            return self._error_result("Seller agent failed to produce disclosure")

        omega_hat = disclosure_msg.disclosure.disclosed_value
        logger.info(f"Seller disclosed omega_hat={omega_hat:.4f}")

        # Phase 2: Buyer evaluation → v_b (1 API call)
        logger.info("Phase 2: Buyer agent evaluating disclosure")
        self._emit_progress("buyer_evaluation", {})
        buyer_msg = self.buyer_agent.evaluate_disclosure(
            disclosure_msg.disclosure, round_num=1
        )
        self.transcript.messages.append(buyer_msg)

        v_b = self.buyer_agent.assessed_value
        if v_b is None:
            return self._error_result("Buyer agent failed to produce assessed_value")

        logger.info(f"Buyer assessed value v_b={v_b:.4f}")

        # Check deal viability before entering negotiation
        if not check_deal_viability(v_b, alpha_0, omega_hat):
            return self._no_deal_result(
                omega_hat, v_b,
                f"No surplus: buyer valuation {v_b:.4f} "
                f"< seller reservation {alpha_0 * omega_hat:.4f}",
            )

        # Phase 3: Multi-round negotiation (if enabled)
        rounds_completed = 1
        candidate_price = None

        if self.config.max_rounds > 1:
            self._emit_progress("nash_resolution", {})
            for round_num in range(2, self.config.max_rounds + 1):
                self._emit_progress("round", {"number": round_num, "phase": "buyer_offer"})
                logger.info(f"Round {round_num}: Buyer making offer")

                # Buyer makes offer
                seller_explanation = ""
                if len(self.transcript.messages) > 0:
                    last = self.transcript.messages[-1]
                    seller_explanation = last.explanation or ""

                buyer_offer = self.buyer_agent.make_offer(
                    disclosure_msg.disclosure, round_num,
                    seller_explanation=seller_explanation,
                )
                if not buyer_offer or not buyer_offer.price_proposal:
                    logger.info(f"Round {round_num}: Buyer declined to offer, breaking")
                    break
                self.transcript.messages.append(buyer_offer)

                offered_price = buyer_offer.price_proposal.proposed_price
                logger.info(f"Round {round_num}: Buyer offers {offered_price:.4f}")

                # Seller evaluates offer
                self._emit_progress("round", {"number": round_num, "phase": "seller_response"})
                seller_response = self.seller_agent.evaluate_offer(
                    offered_price,
                    buyer_offer.explanation or "",
                    round_num,
                )
                self.transcript.messages.append(seller_response)

                # Check seller's response
                if seller_response.raw_response:
                    action = seller_response.raw_response.get("input", {}).get("action", "accept")
                else:
                    action = "accept"

                self._emit_progress("round", {"number": round_num, "phase": "seller_response", "action": action})
                logger.info(f"Round {round_num}: Seller action={action}")

                if action == "accept":
                    candidate_price = offered_price
                    rounds_completed = round_num
                    break
                elif action == "reject":
                    rounds_completed = round_num
                    break
                # action == "counter" → continue to next round

                rounds_completed = round_num

        # Phase 4: Final resolution
        self._emit_progress("nash_resolution", {})

        # If multi-round produced an accepted price, use it
        if candidate_price is not None:
            price = candidate_price
        else:
            # Fall back to bilateral Nash backstop
            price = compute_bilateral_price(alpha_0, omega_hat, v_b)

        # Check budget cap
        if not check_budget_cap(price, self.config.budget_cap):
            return self._no_deal_result(
                omega_hat, v_b,
                f"Price {price:.4f} exceeds budget {self.config.budget_cap}",
                rounds=rounds_completed,
            )

        seller_payoff = compute_seller_payoff(price, alpha_0, omega, omega_hat)
        buyer_payoff = v_b - price

        result = NegotiationResult(
            outcome=NegotiationOutcomeType.AGREEMENT,
            final_price=price,
            omega_hat=omega_hat,
            theta=self.theta,
            phi=self.phi,
            seller_payoff=seller_payoff,
            buyer_payoff=buyer_payoff,
            buyer_valuation=v_b,
            negotiation_rounds=rounds_completed,
            reason="Bilateral Nash bargaining equilibrium reached",
        )

        self.transcript.result = result
        logger.info(f"Negotiation complete: {result.outcome.value} in {rounds_completed} rounds")
        return result

    def _no_deal_result(
        self, omega_hat: float, v_b: float, reason: str, rounds: int = 1
    ) -> NegotiationResult:
        result = NegotiationResult(
            outcome=NegotiationOutcomeType.NO_DEAL,
            final_price=None,
            omega_hat=omega_hat,
            theta=self.theta,
            phi=self.phi,
            seller_payoff=None,
            buyer_payoff=None,
            buyer_valuation=v_b,
            negotiation_rounds=rounds,
            reason=reason,
        )
        self.transcript.result = result
        logger.info(f"Negotiation complete: {result.outcome.value}")
        return result

    def _emit_progress(self, phase: str, data: dict):
        """Emit a progress event if a callback is registered."""
        if self._progress_callback:
            try:
                self._progress_callback(phase, data)
            except Exception:
                logger.warning("Progress callback failed for phase=%s", phase)

    def _error_result(self, reason: str) -> NegotiationResult:
        omega_hat = self.seller_agent.disclosed_omega_hat or 0.0
        result = NegotiationResult(
            outcome=NegotiationOutcomeType.ERROR,
            final_price=None,
            omega_hat=omega_hat,
            theta=self.theta,
            phi=self.phi,
            seller_payoff=None,
            buyer_payoff=None,
            reason=reason,
        )
        self.transcript.result = result
        return result
