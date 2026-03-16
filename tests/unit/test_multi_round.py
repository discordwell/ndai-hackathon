"""Tests for multi-round negotiation."""

from unittest.mock import MagicMock

import pytest

from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.negotiation.engine import NegotiationOutcomeType, SecurityParams
from ndai.enclave.session import NegotiationSession, SessionConfig


def _mock_tool_response(name: str, input_data: dict):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = name
    tool_block.input = input_data
    tool_block.id = f"mock_{name}"

    response = MagicMock()
    response.content = [tool_block]
    return response


def _make_multi_round_llm(
    assessed_value: float = 0.65,
    offer_price: float = 0.4,
    seller_action: str = "accept",
):
    """Create a mock LLM that supports multi-round: disclosure, evaluation, offer, seller response."""
    llm = MagicMock(spec=LLMClient)

    seller_disclosure = _mock_tool_response(
        "make_disclosure",
        {
            "summary": "A quantum-resistant protocol",
            "technical_details": "Uses ring-LWE with NTT-friendly primes.",
            "disclosed_value": 0.7,
            "withheld_aspects": ["NTT optimization"],
            "reasoning": "Disclosing most to maximize price.",
        },
    )

    buyer_eval = _mock_tool_response(
        "evaluate_invention",
        {
            "assessed_value": assessed_value,
            "strengths": ["Novel approach"],
            "concerns": ["Prototype stage"],
            "reasoning": "Strong technical merit.",
        },
    )

    buyer_offer = _mock_tool_response(
        "make_offer",
        {
            "proposed_price": offer_price,
            "explanation": f"I offer {offer_price}",
            "reasoning": "Fair price based on assessment.",
        },
    )

    seller_response = _mock_tool_response(
        "respond_to_offer",
        {
            "action": seller_action,
            "explanation": f"I {seller_action} the offer.",
            "private_reasoning": "Reasonable price.",
            "counter_price": offer_price + 0.05 if seller_action == "counter" else None,
        },
    )

    responses = [seller_disclosure, buyer_eval, buyer_offer, seller_response]
    # If counter, add another round
    if seller_action == "counter":
        buyer_offer_2 = _mock_tool_response(
            "make_offer",
            {
                "proposed_price": offer_price + 0.03,
                "explanation": "Revised offer",
                "reasoning": "Meeting in the middle.",
            },
        )
        seller_accept = _mock_tool_response(
            "respond_to_offer",
            {
                "action": "accept",
                "explanation": "Accepted.",
                "private_reasoning": "Good enough.",
            },
        )
        responses.extend([buyer_offer_2, seller_accept])

    llm.create_message.side_effect = responses

    def extract_tool(resp):
        for block in resp.content:
            if block.type == "tool_use":
                return {"name": block.name, "input": block.input, "id": block.id}
        return None

    llm.extract_tool_use.side_effect = extract_tool
    return llm


@pytest.fixture
def invention():
    return InventionSubmission(
        title="Quantum-Resistant Lattice Key Exchange",
        full_description="A novel key exchange protocol.",
        technical_domain="cryptography",
        novelty_claims=["New ring-LWE variant"],
        prior_art_known=["CRYSTALS-Kyber"],
        potential_applications=["TLS 1.4"],
        development_stage="prototype",
        self_assessed_value=0.75,
        outside_option_value=0.3,
        confidential_sections=["NTT trick"],
        max_disclosure_fraction=0.9,
    )


@pytest.fixture
def security_params():
    return SecurityParams(k=3, p=0.005, c=7_500_000_000)


class TestMultiRound:
    def test_single_round_when_max_1(self, invention, security_params):
        """When max_rounds=1, no multi-round loop runs."""
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=security_params,
            max_rounds=1,
            anthropic_api_key="test-key",
        )
        # Only 2 LLM calls needed for single round
        llm = MagicMock(spec=LLMClient)
        llm.create_message.side_effect = [
            _mock_tool_response("make_disclosure", {
                "summary": "test", "technical_details": "test",
                "disclosed_value": 0.7, "withheld_aspects": [],
                "reasoning": "test",
            }),
            _mock_tool_response("evaluate_invention", {
                "assessed_value": 0.65, "strengths": [],
                "concerns": [], "reasoning": "test",
            }),
        ]
        llm.extract_tool_use.side_effect = lambda r: {
            "name": r.content[0].name,
            "input": r.content[0].input,
            "id": r.content[0].id,
        }

        session = NegotiationSession(config)
        session.seller_agent.llm = llm
        session.buyer_agent.llm = llm

        result = session.run()
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.negotiation_rounds == 1
        assert len(session.transcript.messages) == 2

    def test_multi_round_accept(self, invention, security_params):
        """Buyer offers, seller accepts in round 2."""
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=security_params,
            max_rounds=5,
            anthropic_api_key="test-key",
        )
        llm = _make_multi_round_llm(
            assessed_value=0.65,
            offer_price=0.4,
            seller_action="accept",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = llm
        session.buyer_agent.llm = llm

        result = session.run()
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price == pytest.approx(0.4)
        assert result.negotiation_rounds == 2

    def test_multi_round_counter_then_accept(self, invention, security_params):
        """Seller counters in round 2, buyer re-offers, seller accepts in round 3."""
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=security_params,
            max_rounds=5,
            anthropic_api_key="test-key",
        )
        llm = _make_multi_round_llm(
            assessed_value=0.65,
            offer_price=0.4,
            seller_action="counter",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = llm
        session.buyer_agent.llm = llm

        result = session.run()
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        # Price should be the accepted offer from round 3 (0.4 + 0.03 = 0.43)
        assert result.final_price == pytest.approx(0.43)
        assert result.negotiation_rounds == 3

    def test_budget_cap_clamps_buyer_offer(self, invention, security_params):
        """Buyer's offer is clamped to budget cap."""
        config = SessionConfig(
            invention=invention,
            budget_cap=0.01,  # Very low — buyer's offer clamped to 0.01
            security_params=security_params,
            max_rounds=5,
            anthropic_api_key="test-key",
        )
        llm = _make_multi_round_llm(
            assessed_value=0.65,
            offer_price=0.4,
            seller_action="accept",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = llm
        session.buyer_agent.llm = llm

        result = session.run()
        # Buyer's make_offer clamps proposed_price to budget_cap=0.01
        # Seller accepts 0.01, which is within budget
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price == pytest.approx(0.01)
