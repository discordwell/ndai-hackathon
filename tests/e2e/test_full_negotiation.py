"""End-to-end test: full NDAI negotiation with mocked LLM.

Tests the complete flow: invention submission -> agent negotiation -> outcome,
using the SimulatedTEE and mocked Claude responses.
"""

from unittest.mock import MagicMock

import pytest

from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    SecurityParams,
    compute_baseline_payoffs,
)
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


def _make_mock_llm():
    """Create a mock LLM that produces valid seller disclosure and buyer offer.

    omega=0.75, alpha_0=0.3 => theta=0.65, floor=0.4875
    Seller discloses omega_hat=0.7 => equilibrium P*=0.65*0.7=0.455
    Buyer offers 0.50 (above floor) => accepted immediately.
    """
    llm = MagicMock(spec=LLMClient)

    # Seller disclosure response
    seller_disclosure = _mock_tool_response(
        "make_disclosure",
        {
            "summary": "A quantum-resistant lattice-based key exchange protocol",
            "technical_details": (
                "Uses ring-LWE with NTT-friendly primes for O(n log n) performance. "
                "Achieves 30% tighter security reduction than Kyber."
            ),
            "disclosed_value": 0.7,
            "withheld_aspects": ["NTT optimization trick", "Security proof technique"],
            "reasoning": "Disclosing most of the invention to maximize price.",
        },
    )

    # Buyer evaluation response
    buyer_eval = _mock_tool_response(
        "evaluate_invention",
        {
            "assessed_value": 0.65,
            "strengths": ["Novel ring-LWE variant", "Formal verification"],
            "concerns": ["Prototype stage", "Withheld optimization details"],
            "reasoning": "Strong technical merit but unproven at scale.",
        },
    )

    # Buyer offer: 0.50, above seller floor 0.4875
    buyer_offer = _mock_tool_response(
        "make_offer",
        {
            "price": 0.50,
            "explanation": "Fair price above equilibrium.",
            "private_reasoning": "Offering above floor to close deal.",
        },
    )

    # Seller accept response (used if negotiation continues)
    seller_accept = _mock_tool_response(
        "respond_to_offer",
        {
            "action": "accept",
            "explanation": "Price meets our threshold. Accepted.",
            "private_reasoning": "Above minimum acceptable price.",
        },
    )

    # Provide enough responses for multi-round cases
    # After the main sequence, repeat the accept response
    responses = [seller_disclosure, buyer_eval, buyer_offer, seller_accept]
    for _ in range(10):
        responses.append(seller_accept)
        responses.append(buyer_offer)

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
        full_description=(
            "A novel key exchange protocol based on structured lattices that achieves "
            "post-quantum security with O(n log n) computation complexity."
        ),
        technical_domain="cryptography",
        novelty_claims=[
            "New ring-LWE variant with 30% tighter security reduction",
            "Efficient NTT-friendly implementation",
            "Formal verification in Lean4",
        ],
        prior_art_known=["CRYSTALS-Kyber", "NewHope"],
        potential_applications=["TLS 1.4", "Secure messaging", "IoT auth"],
        development_stage="prototype",
        self_assessed_value=0.75,
        outside_option_value=0.3,
        confidential_sections=["NTT optimization trick", "Security proof technique"],
        max_disclosure_fraction=0.9,
    )


@pytest.fixture
def security_params():
    return SecurityParams(k=3, p=0.005, c=7_500_000_000)


class TestFullNegotiation:
    def test_successful_agreement(self, invention, security_params):
        """Complete negotiation ending in agreement."""
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=security_params,
            max_rounds=5,
            anthropic_api_key="test-key",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = _make_mock_llm()
        session.buyer_agent.llm = session.seller_agent.llm

        result = session.run()

        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price is not None
        assert result.final_price > 0
        assert result.omega_hat > 0
        assert result.omega_hat <= invention.self_assessed_value
        assert result.seller_payoff is not None
        assert result.buyer_payoff is not None
        assert len(session.transcript.messages) >= 2

    def test_pareto_improvement(self, invention, security_params):
        """NDAI outcome Pareto-dominates the no-disclosure baseline."""
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=security_params,
            anthropic_api_key="test-key",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = _make_mock_llm()
        session.buyer_agent.llm = session.seller_agent.llm

        result = session.run()
        baseline_seller, baseline_buyer = compute_baseline_payoffs(
            invention.self_assessed_value, invention.outside_option_value
        )

        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.seller_payoff is not None
        assert result.buyer_payoff is not None
        # Both parties should be strictly better off
        assert result.seller_payoff > baseline_seller
        assert result.buyer_payoff > baseline_buyer

    def test_budget_cap_prevents_agreement(self, invention, security_params):
        """When budget cap is too low, no deal is reached."""
        config = SessionConfig(
            invention=invention,
            budget_cap=0.01,  # Very low budget
            security_params=security_params,
            anthropic_api_key="test-key",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = _make_mock_llm()
        session.buyer_agent.llm = session.seller_agent.llm

        result = session.run()

        assert result.outcome == NegotiationOutcomeType.NO_DEAL
        assert result.final_price is None

    def test_deterministic_result_matches(self, invention, security_params):
        """The session also computes the deterministic (no-LLM) result for comparison."""
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=security_params,
            anthropic_api_key="test-key",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = _make_mock_llm()
        session.buyer_agent.llm = session.seller_agent.llm

        result = session.run()
        det = session.transcript.deterministic_result

        assert det is not None
        assert det.outcome == NegotiationOutcomeType.AGREEMENT
        assert det.theta == result.theta
        assert det.phi == result.phi

    def test_transcript_records_messages(self, invention, security_params):
        """Session transcript captures the negotiation history."""
        config = SessionConfig(
            invention=invention,
            budget_cap=1.0,
            security_params=security_params,
            anthropic_api_key="test-key",
        )
        session = NegotiationSession(config)
        session.seller_agent.llm = _make_mock_llm()
        session.buyer_agent.llm = session.seller_agent.llm

        session.run()

        # Should have at least seller disclosure + buyer offer
        assert len(session.transcript.messages) >= 2
        # First message should be seller's disclosure
        assert session.transcript.messages[0].disclosure is not None
        # Second message should have buyer's price proposal
        assert session.transcript.messages[1].price_proposal is not None
