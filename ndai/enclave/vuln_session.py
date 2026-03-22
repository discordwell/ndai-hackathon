"""Vulnerability negotiation session orchestrator.

Runs inside the TEE (or simulated TEE). Wires together:
- VulnSellerAgent (graduated disclosure)
- VulnBuyerAgent (severity triage + pricing)
- Shelf-life engine (time-decaying value model)
- Protocol state machine (round management)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ndai.enclave.agents.base_agent import AgentMessage, AgentRole, VulnDisclosure, VulnerabilitySubmission
from ndai.enclave.agents.vuln_buyer_agent import VulnBuyerAgent
from ndai.enclave.agents.vuln_seller_agent import VulnSellerAgent
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.negotiation.shelf_life import (
    ShelfLifeParams,
    VulnNegotiationResult,
    VulnOutcomeType,
    check_vuln_deal_viability,
    compute_current_value,
    compute_vuln_bilateral_price,
    disclosure_to_fraction,
    estimate_patch_probability,
    get_decay_rate,
)

logger = logging.getLogger(__name__)


@dataclass
class VulnSessionConfig:
    """Configuration for a vulnerability negotiation session."""

    vulnerability: VulnerabilitySubmission
    budget_cap: float
    max_rounds: int = 5
    llm_provider: str = "openai"
    api_key: str = ""
    llm_model: str = "gpt-4o"
    software_category: str = "default"
    cdp_client: Any | None = None


@dataclass
class VulnSessionTranscript:
    """Full record of a vulnerability negotiation session."""

    messages: list[AgentMessage] = field(default_factory=list)
    result: VulnNegotiationResult | None = None


class VulnNegotiationSession:
    """Orchestrates a complete vulnerability marketplace negotiation.

    Flow:
    1. Compute current value V(t) via shelf-life decay
    2. Seller agent decides disclosure level (0-3) — 1 API call
    3. Buyer agent evaluates vulnerability (v_b) — 1 API call
    4. Multi-round price negotiation (optional)
    5. Bilateral Nash resolution: P* = (v_b + alpha_0 * omega_hat) / 2
    """

    def __init__(self, config: VulnSessionConfig, progress_callback=None):
        self.config = config
        self._progress_callback = progress_callback
        self.transcript = VulnSessionTranscript()

        vuln = config.vulnerability

        # Compute shelf-life parameters
        days = self._days_since_discovery(vuln.discovery_date)
        category = vuln.software_category or config.software_category
        lambda_rate = get_decay_rate(category)
        patch_prob = estimate_patch_probability(days, category)
        exclusivity_premium = 1.3 if vuln.exclusivity == "exclusive" else 1.0

        self.shelf_life = ShelfLifeParams(
            v_0=vuln.cvss_self_assessed / 10.0,  # Normalize CVSS [0,10] to [0,1]
            lambda_rate=lambda_rate,
            days_since_discovery=days,
            patch_probability=patch_prob,
            exclusivity_premium=exclusivity_premium,
        )
        self.current_value = compute_current_value(self.shelf_life)
        self.alpha_0 = vuln.outside_option_value

        # Create LLM client
        api_key = config.api_key
        if config.llm_provider == "openai":
            from ndai.enclave.agents.openai_llm_client import OpenAILLMClient
            llm = OpenAILLMClient(api_key=api_key, model=config.llm_model)
        else:
            llm = LLMClient(api_key=api_key, model=config.llm_model)

        self.seller_agent = VulnSellerAgent(
            vuln=vuln,
            llm_client=llm,
            current_value=self.current_value,
        )
        self.buyer_agent = VulnBuyerAgent(
            budget_cap=config.budget_cap,
            alpha_0=self.alpha_0,
            llm_client=llm,
        )

    def run(self) -> VulnNegotiationResult:
        """Execute the full vulnerability negotiation protocol."""
        logger.info(
            "Starting vuln negotiation: V(t)=%.4f, alpha_0=%.2f, budget=%.4f",
            self.current_value, self.alpha_0, self.config.budget_cap,
        )

        # Phase 1: Seller disclosure → level (0-3), 1 API call
        logger.info("Phase 1: Seller agent deciding disclosure level")
        self._emit_progress("seller_disclosure", {})
        disclosure_msg = self.seller_agent.decide_disclosure()
        self.transcript.messages.append(disclosure_msg)

        # Extract VulnDisclosure from raw_response
        vuln_disclosure = self._extract_disclosure(disclosure_msg)
        if not vuln_disclosure:
            return self._error_result("Seller agent failed to produce disclosure")

        level = vuln_disclosure.level
        fraction = disclosure_to_fraction(level)
        omega_hat = self.current_value * fraction
        logger.info("Seller disclosed level=%d, omega_hat=%.4f", level, omega_hat)

        # Phase 2: Buyer evaluation → v_b, 1 API call
        logger.info("Phase 2: Buyer agent evaluating vulnerability")
        self._emit_progress("buyer_evaluation", {})
        buyer_msg = self.buyer_agent.evaluate_disclosure(vuln_disclosure, round_num=1)
        self.transcript.messages.append(buyer_msg)

        v_b = self.buyer_agent.assessed_value
        if v_b is None:
            return self._error_result("Buyer agent failed to produce assessed_value")

        logger.info("Buyer assessed value v_b=%.4f", v_b)

        # Check deal viability
        if not check_vuln_deal_viability(v_b, self.alpha_0, omega_hat):
            return self._no_deal_result(
                level, fraction, v_b,
                f"No surplus: buyer valuation {v_b:.4f} "
                f"< seller floor {self.alpha_0 * omega_hat:.4f}",
            )

        # Phase 3: Multi-round negotiation
        rounds_completed = 1
        candidate_price = None

        if self.config.max_rounds > 1:
            self._emit_progress("negotiation_rounds", {})
            for round_num in range(2, self.config.max_rounds + 1):
                self._emit_progress("round", {"number": round_num, "phase": "buyer_offer"})
                logger.info("Round %d: Buyer making offer", round_num)

                # Build seller context from last message (includes counter-offer info)
                seller_explanation = ""
                if self.transcript.messages:
                    last_msg = self.transcript.messages[-1]
                    seller_explanation = last_msg.explanation or ""
                    # If seller countered in prior round, include counter price
                    if last_msg.price_proposal and last_msg.role == AgentRole.VULN_SELLER:
                        seller_explanation += (
                            f"\nSeller's counter-offer: {last_msg.price_proposal.proposed_price:.4f}"
                        )

                buyer_offer = self.buyer_agent.make_offer(
                    vuln_disclosure, round_num,
                    seller_explanation=seller_explanation,
                )
                if not buyer_offer or not buyer_offer.price_proposal:
                    logger.info("Round %d: Buyer declined to offer", round_num)
                    break
                self.transcript.messages.append(buyer_offer)

                offered_price = buyer_offer.price_proposal.proposed_price
                logger.info("Round %d: Buyer offers %.4f", round_num, offered_price)

                # Seller evaluates
                self._emit_progress("round", {"number": round_num, "phase": "seller_response"})
                seller_response = self.seller_agent.evaluate_offer(
                    offered_price,
                    buyer_offer.explanation or "",
                    round_num,
                )
                self.transcript.messages.append(seller_response)

                if seller_response.raw_response:
                    action = seller_response.raw_response.get("input", {}).get("action", "accept")
                else:
                    action = "accept"

                logger.info("Round %d: Seller action=%s", round_num, action)

                if action == "accept":
                    candidate_price = offered_price
                    rounds_completed = round_num
                    break
                elif action == "reject":
                    rounds_completed = round_num
                    break
                # action == "counter" → counter price stored in seller_response.price_proposal,
                # fed to buyer's next make_offer() via seller_explanation above

                rounds_completed = round_num

        # Phase 4: Final resolution
        self._emit_progress("nash_resolution", {})

        if candidate_price is not None:
            price = candidate_price
        else:
            price = compute_vuln_bilateral_price(self.alpha_0, omega_hat, v_b)

        if price > self.config.budget_cap:
            return self._no_deal_result(
                level, fraction, v_b,
                f"Price {price:.4f} exceeds budget {self.config.budget_cap}",
                rounds=rounds_completed,
            )

        seller_payoff = price + self.alpha_0 * (self.current_value - omega_hat)
        buyer_payoff = v_b - price

        result = VulnNegotiationResult(
            outcome=VulnOutcomeType.AGREEMENT,
            final_price=price,
            current_value=self.current_value,
            disclosure_level=level,
            disclosure_fraction=fraction,
            seller_payoff=seller_payoff,
            buyer_payoff=buyer_payoff,
            buyer_valuation=v_b,
            negotiation_rounds=rounds_completed,
            reason="Bilateral Nash bargaining equilibrium reached",
        )

        self.transcript.result = result
        logger.info("Negotiation complete: %s in %d rounds", result.outcome.value, rounds_completed)
        return result

    def _extract_disclosure(self, msg: AgentMessage) -> VulnDisclosure | None:
        """Extract VulnDisclosure from agent message raw_response."""
        if msg.raw_response and "vuln_disclosure" in msg.raw_response:
            d = msg.raw_response["vuln_disclosure"]
            return VulnDisclosure(
                level=d["level"],
                level_fraction=d["level_fraction"],
                vulnerability_class=d["vulnerability_class"],
                impact_type=d["impact_type"],
                affected_component=d.get("affected_component"),
                attack_surface=d.get("attack_surface"),
                trigger_conditions=d.get("trigger_conditions"),
                constraints=d.get("constraints"),
                poc_summary=d.get("poc_summary"),
                withheld_aspects=d.get("withheld_aspects", []),
            )
        return None

    def _no_deal_result(
        self, level: int, fraction: float, v_b: float, reason: str, rounds: int = 1
    ) -> VulnNegotiationResult:
        result = VulnNegotiationResult(
            outcome=VulnOutcomeType.NO_DEAL,
            final_price=None,
            current_value=self.current_value,
            disclosure_level=level,
            disclosure_fraction=fraction,
            seller_payoff=None,
            buyer_payoff=None,
            buyer_valuation=v_b,
            negotiation_rounds=rounds,
            reason=reason,
        )
        self.transcript.result = result
        logger.info("Negotiation complete: %s", result.outcome.value)
        return result

    def _error_result(self, reason: str) -> VulnNegotiationResult:
        result = VulnNegotiationResult(
            outcome=VulnOutcomeType.ERROR,
            final_price=None,
            current_value=self.current_value,
            disclosure_level=0,
            disclosure_fraction=0.0,
            seller_payoff=None,
            buyer_payoff=None,
            reason=reason,
        )
        self.transcript.result = result
        return result

    def _emit_progress(self, phase: str, data: dict):
        if self._progress_callback:
            try:
                self._progress_callback(phase, data)
            except Exception:
                logger.warning("Progress callback failed for phase=%s", phase)

    @staticmethod
    def _days_since_discovery(discovery_date: str) -> float:
        """Compute days elapsed since discovery."""
        try:
            disc = datetime.fromisoformat(discovery_date.replace("Z", "+00:00"))
            if disc.tzinfo is None:
                disc = disc.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - disc
            return max(delta.total_seconds() / 86400.0, 0.0)
        except (ValueError, TypeError):
            return 0.0
