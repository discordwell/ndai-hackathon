"""Regression tests for the seller's hard acceptance floor in multi-round sessions.

SellerAgent.evaluate_offer enforces the floor (P >= alpha_0 * omega_hat) by
short-circuiting below-floor offers WITHOUT calling the LLM, returning a
counter-at-floor message with raw_response=None. The session previously read a
missing raw_response as action="accept", so a below-floor lowball was silently
accepted as the final deal price. These tests pin the corrected behavior.
"""

from unittest.mock import MagicMock

from ndai.enclave.agents.base_agent import (
    AgentMessage,
    AgentRole,
    InventionDisclosure,
    InventionSubmission,
    PriceProposal,
)
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.agents.seller_agent import SellerAgent
from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    SecurityParams,
)
from ndai.enclave.session import NegotiationSession, SessionConfig


def _make_invention(**overrides) -> InventionSubmission:
    defaults = {
        "title": "Test Invention",
        "full_description": "A novel approach to testing.",
        "technical_domain": "software",
        "novelty_claims": ["Novel test approach"],
        "prior_art_known": ["Existing tests"],
        "potential_applications": ["Better testing"],
        "development_stage": "prototype",
        "self_assessed_value": 0.5,  # omega
        "outside_option_value": 0.8,  # alpha_0
        "confidential_sections": ["Secret sauce"],
        "max_disclosure_fraction": 1.0,
    }
    defaults.update(overrides)
    return InventionSubmission(**defaults)


class TestSellerActionDerivation:
    def test_below_floor_counter_is_not_accept(self):
        """A real below-floor evaluate_offer response must read as 'counter'."""
        invention = _make_invention()
        seller = SellerAgent(
            invention=invention,
            llm_client=MagicMock(spec=LLMClient),
            security_threshold=1.0,
        )
        seller.disclosed_omega_hat = 0.5  # floor = alpha_0 * omega_hat = 0.40

        # Offer below the floor — evaluate_offer early-returns without the LLM.
        response = seller.evaluate_offer(price=0.10, buyer_explanation="lowball", round_num=2)
        assert response.raw_response is None  # hard-floor branch never calls the LLM
        assert response.price_proposal is not None

        assert NegotiationSession._seller_action(response) == "counter"

    def test_reads_llm_action_from_raw_response(self):
        for action in ("accept", "counter", "reject"):
            response = AgentMessage(
                role=AgentRole.SELLER,
                round_number=2,
                raw_response={"input": {"action": action}},
            )
            assert NegotiationSession._seller_action(response) == action

    def test_bare_response_defaults_to_accept(self):
        """No raw_response and no counter proposal (above-floor fallback) → accept."""
        response = AgentMessage(role=AgentRole.SELLER, round_number=2, explanation="Accepted.")
        assert NegotiationSession._seller_action(response) == "accept"


class TestBelowFloorNotAcceptedEndToEnd:
    def test_lowball_offer_never_becomes_below_floor_agreement(self):
        """Driving a full session where the buyer always lowballs below the floor.

        With the bug, the seller's below-floor counter was read as 'accept' and
        the 0.10 lowball became the final price. The mechanism must instead fall
        back to the bilateral Nash backstop, which respects the floor.
        """
        invention = _make_invention()  # omega=0.5, alpha_0=0.8
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=SecurityParams(k=3, p=0.1, c=10.0),
            max_rounds=3,
            api_key="test-key",
        )
        session = NegotiationSession(config)

        omega_hat = 0.5
        floor = invention.outside_option_value * omega_hat  # 0.8 * 0.5 = 0.40
        v_b = 0.5  # viable: v_b >= alpha_0 * omega_hat (0.40)

        # Seller discloses omega_hat (use the real evaluate_offer / floor logic).
        disclosure = AgentMessage(
            role=AgentRole.SELLER,
            round_number=0,
            disclosure=InventionDisclosure(
                summary="s",
                technical_details="t",
                disclosed_value=omega_hat,
                disclosure_fraction=1.0,
                withheld_aspects=[],
            ),
        )
        session.seller_agent.decide_disclosure = lambda: disclosure
        session.seller_agent.disclosed_omega_hat = omega_hat

        def _evaluate_disclosure(_disclosure, round_num=1):
            session.buyer_agent.assessed_value = v_b
            return AgentMessage(role=AgentRole.BUYER, round_number=round_num)

        session.buyer_agent.evaluate_disclosure = _evaluate_disclosure

        def _make_offer(_disclosure, round_num, seller_explanation=""):
            return AgentMessage(
                role=AgentRole.BUYER,
                round_number=round_num,
                price_proposal=PriceProposal(
                    proposed_price=0.10, reasoning="lowball", confidence=0.9
                ),
            )

        session.buyer_agent.make_offer = _make_offer

        result = session.run()

        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price is not None
        # The hard floor must hold: never settle below alpha_0 * omega_hat.
        assert result.final_price >= floor - 1e-9
        # And specifically never at the buyer's below-floor lowball.
        assert result.final_price > 0.10

    def test_budget_below_floor_yields_no_deal(self):
        """If the buyer's budget can't reach the seller's floor, it's NO_DEAL.

        With the bug, the below-floor lowball was 'accepted' and produced a
        bogus sub-floor agreement. Correctly, the seller counters every round
        and the bilateral backstop price exceeds the budget cap → no deal.
        """
        invention = _make_invention()  # omega=0.5, alpha_0=0.8
        config = SessionConfig(
            invention=invention,
            budget_cap=0.20,  # below both the floor (0.40) and the backstop (0.45)
            security_params=SecurityParams(k=3, p=0.1, c=10.0),
            max_rounds=3,
            api_key="test-key",
        )
        session = NegotiationSession(config)

        omega_hat = 0.5
        v_b = 0.5  # viable surplus exists, but no price within budget clears the floor

        disclosure = AgentMessage(
            role=AgentRole.SELLER,
            round_number=0,
            disclosure=InventionDisclosure(
                summary="s",
                technical_details="t",
                disclosed_value=omega_hat,
                disclosure_fraction=1.0,
                withheld_aspects=[],
            ),
        )
        session.seller_agent.decide_disclosure = lambda: disclosure
        session.seller_agent.disclosed_omega_hat = omega_hat

        def _evaluate_disclosure(_disclosure, round_num=1):
            session.buyer_agent.assessed_value = v_b
            return AgentMessage(role=AgentRole.BUYER, round_number=round_num)

        session.buyer_agent.evaluate_disclosure = _evaluate_disclosure
        session.buyer_agent.make_offer = lambda _d, round_num, seller_explanation="": AgentMessage(
            role=AgentRole.BUYER,
            round_number=round_num,
            price_proposal=PriceProposal(proposed_price=0.10, reasoning="lowball", confidence=0.9),
        )

        result = session.run()

        assert result.outcome == NegotiationOutcomeType.NO_DEAL
        assert result.final_price is None
