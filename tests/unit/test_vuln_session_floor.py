"""Regression tests for the seller's hard acceptance floor in vuln-negotiation sessions.

This mirrors ``test_session_floor.py`` (invention negotiation) for the *vulnerability*
marketplace path. ``VulnSellerAgent.evaluate_offer`` enforces the floor
(P >= alpha_0 * omega_hat) by short-circuiting below-floor offers WITHOUT calling
the LLM, returning a counter-at-floor message with ``raw_response=None``.
``VulnNegotiationSession.run`` previously read a missing ``raw_response`` as
``action="accept"``, so a below-floor lowball was silently accepted as the final
deal price — violating the seller's documented acceptance threshold. These tests
pin the corrected behavior (the ``_seller_action`` helper ported from session.py).
"""

from unittest.mock import MagicMock, patch

from ndai.enclave.agents.base_agent import (
    AgentMessage,
    AgentRole,
    PriceProposal,
    VulnDisclosure,
    VulnerabilitySubmission,
)
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.agents.vuln_seller_agent import VulnSellerAgent
from ndai.enclave.negotiation.shelf_life import VulnOutcomeType, disclosure_to_fraction
from ndai.enclave.vuln_session import VulnNegotiationSession, VulnSessionConfig


def _make_vuln(**overrides) -> VulnerabilitySubmission:
    defaults = dict(
        target_software="Apache httpd",
        target_version="2.4.52",
        vulnerability_class="CWE-787",
        impact_type="RCE",
        affected_component="mod_proxy",
        cvss_self_assessed=9.0,
        discovery_date="2026-03-01",
        patch_status="unpatched",
        exclusivity="exclusive",
        outside_option_value=0.3,  # alpha_0
        max_disclosure_level=3,
        software_category="web_server",
    )
    defaults.update(overrides)
    return VulnerabilitySubmission(**defaults)


def _make_config(**overrides) -> VulnSessionConfig:
    defaults = dict(
        vulnerability=_make_vuln(),
        budget_cap=1.0,
        max_rounds=3,
        llm_provider="openai",
        api_key="test-key",
        llm_model="gpt-4o",
    )
    defaults.update(overrides)
    return VulnSessionConfig(**defaults)


def _disclosure_msg(level: int = 3) -> AgentMessage:
    """A seller disclosure message shaped like the real decide_disclosure output."""
    disclosure = VulnDisclosure(
        level=level,
        level_fraction=disclosure_to_fraction(level),
        vulnerability_class="CWE-787",
        impact_type="RCE",
        affected_component="mod_proxy",
        attack_surface="HTTP request handling",
        trigger_conditions="Crafted chunked header",
        constraints="Network access required",
        poc_summary="Heap overflow in length parsing",
        withheld_aspects=[],
    )
    return AgentMessage(
        role=AgentRole.VULN_SELLER,
        round_number=0,
        raw_response={"vuln_disclosure": disclosure.__dict__},
    )


class TestSellerActionDerivation:
    def test_below_floor_counter_is_not_accept(self):
        """A real below-floor evaluate_offer response must read as 'counter'."""
        seller = VulnSellerAgent(
            vuln=_make_vuln(),  # alpha_0 = 0.3
            llm_client=MagicMock(spec=LLMClient),
            current_value=0.6,
        )
        seller.disclosed_omega_hat = 0.6  # floor = alpha_0 * omega_hat = 0.18

        # Offer below the floor — evaluate_offer early-returns without the LLM.
        response = seller.evaluate_offer(price=0.05, buyer_explanation="lowball", round_num=2)
        assert response.raw_response is None  # hard-floor branch never calls the LLM
        assert response.price_proposal is not None  # counters at the floor

        assert VulnNegotiationSession._seller_action(response) == "counter"

    def test_reads_llm_action_from_raw_response(self):
        for action in ("accept", "counter", "reject"):
            response = AgentMessage(
                role=AgentRole.VULN_SELLER,
                round_number=2,
                raw_response={"input": {"action": action}},
            )
            assert VulnNegotiationSession._seller_action(response) == action

    def test_bare_response_defaults_to_accept(self):
        """No raw_response and no counter proposal (above-floor LLM-less fallback) → accept."""
        response = AgentMessage(
            role=AgentRole.VULN_SELLER, round_number=2, explanation="Accepted."
        )
        assert VulnNegotiationSession._seller_action(response) == "accept"


class TestBelowFloorNotAcceptedEndToEnd:
    @staticmethod
    def _build_session(**config_overrides):
        """Construct a session with the LLM stubbed out (patched only during
        construction — current_value and the LLM client are fixed in __init__).
        Tests then replace the negotiation-driving agent methods, keeping the REAL
        seller.evaluate_offer floor logic."""
        with patch(
            "ndai.enclave.agents.openai_llm_client.OpenAILLMClient",
            return_value=MagicMock(),
        ), patch(
            "ndai.enclave.vuln_session.VulnNegotiationSession._days_since_discovery",
            return_value=21.0,
        ):
            return VulnNegotiationSession(_make_config(**config_overrides))

    @staticmethod
    def _wire_lowball(session, v_b: float, lowball: float, level: int = 3):
        omega_hat = session.current_value * disclosure_to_fraction(level)
        session.seller_agent.decide_disclosure = lambda: _disclosure_msg(level)
        session.seller_agent.disclosed_omega_hat = omega_hat

        def _evaluate_disclosure(_disclosure, round_num=1):
            session.buyer_agent.assessed_value = v_b
            return AgentMessage(role=AgentRole.VULN_BUYER, round_number=round_num)

        session.buyer_agent.evaluate_disclosure = _evaluate_disclosure
        session.buyer_agent.make_offer = lambda _d, round_num, seller_explanation="": AgentMessage(
            role=AgentRole.VULN_BUYER,
            round_number=round_num,
            price_proposal=PriceProposal(
                proposed_price=lowball, reasoning="lowball", confidence=0.9
            ),
        )
        return omega_hat

    def test_lowball_offer_never_becomes_below_floor_agreement(self):
        """Buyer lowballs below the floor every round.

        With the bug, the seller's below-floor counter was read as 'accept' and the
        lowball became the final price. Correctly, the mechanism falls back to the
        bilateral Nash backstop, which respects the floor.
        """
        session = self._build_session(budget_cap=1.0)
        cv = session.current_value
        assert cv > 0

        floor = session.alpha_0 * cv  # level 3 → omega_hat = cv
        v_b = floor * 1.5  # viable (v_b >= floor) and within budget
        lowball = floor * 0.5  # below the floor

        self._wire_lowball(session, v_b=v_b, lowball=lowball)

        result = session.run()

        assert result.outcome == VulnOutcomeType.AGREEMENT
        assert result.final_price is not None
        # The hard floor must hold: never settle below alpha_0 * omega_hat.
        assert result.final_price >= floor - 1e-9
        # And specifically never at the buyer's below-floor lowball.
        assert result.final_price > lowball

    def test_budget_below_floor_yields_no_deal(self):
        """If the budget can't reach the seller's floor, the result is NO_DEAL.

        Discriminating: the budget sits *above* the lowball but *below* the
        backstop. With the bug, the below-floor lowball was 'accepted' (and is
        within budget) → a bogus sub-floor agreement. Correctly, the seller
        counters every round and the bilateral backstop (>= floor) exceeds the
        budget → no deal.
        """
        session = self._build_session(budget_cap=1.0)  # placeholder; reset below
        cv = session.current_value
        assert cv > 0

        floor = session.alpha_0 * cv
        v_b = floor * 1.4  # viable; backstop = (v_b + floor)/2 = 1.2 * floor
        lowball = floor * 0.5

        # lowball < budget < backstop: an "accepted" lowball would clear the
        # budget (proving the bug), while the correct backstop does not.
        session.config.budget_cap = floor * 0.8
        assert lowball < session.config.budget_cap < (v_b + floor) / 2

        self._wire_lowball(session, v_b=v_b, lowball=lowball)

        result = session.run()

        assert result.outcome == VulnOutcomeType.NO_DEAL
        assert result.final_price is None
