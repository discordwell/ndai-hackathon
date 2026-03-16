"""Tests for seller and buyer agents with mocked LLM responses."""

from unittest.mock import MagicMock, patch

import pytest

from ndai.enclave.agents.base_agent import (
    AgentRole,
    InventionDisclosure,
    InventionSubmission,
)
from ndai.enclave.agents.buyer_agent import BuyerAgent
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.agents.seller_agent import SellerAgent


def _make_invention(**overrides) -> InventionSubmission:
    defaults = {
        "title": "Test Invention",
        "full_description": "A novel approach to testing.",
        "technical_domain": "software",
        "novelty_claims": ["Novel test approach"],
        "prior_art_known": ["Existing tests"],
        "potential_applications": ["Better testing"],
        "development_stage": "prototype",
        "self_assessed_value": 0.75,
        "outside_option_value": 0.3,
        "confidential_sections": ["Secret sauce"],
        "max_disclosure_fraction": 0.8,
    }
    defaults.update(overrides)
    return InventionSubmission(**defaults)


def _mock_tool_response(name: str, input_data: dict):
    """Create a mock Claude response with a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = name
    tool_block.input = input_data
    tool_block.id = "mock_tool_id"

    response = MagicMock()
    response.content = [tool_block]
    return response


class TestSellerAgent:
    def test_disclosure_clamps_to_omega(self):
        """Hard constraint: disclosed_value <= omega."""
        invention = _make_invention(self_assessed_value=0.5)
        llm = MagicMock(spec=LLMClient)
        llm.create_message.return_value = _mock_tool_response(
            "make_disclosure",
            {
                "summary": "Great invention",
                "technical_details": "Details here",
                "disclosed_value": 0.9,  # Exceeds omega=0.5
                "withheld_aspects": ["secret"],
                "reasoning": "Go big",
            },
        )
        llm.extract_tool_use.return_value = {
            "name": "make_disclosure",
            "input": {
                "summary": "Great invention",
                "technical_details": "Details here",
                "disclosed_value": 0.9,
                "withheld_aspects": ["secret"],
                "reasoning": "Go big",
            },
            "id": "mock_id",
        }

        agent = SellerAgent(invention, llm, security_threshold=1.0)
        msg = agent.decide_disclosure()

        assert msg.disclosure is not None
        assert msg.disclosure.disclosed_value <= 0.5  # Clamped to omega

    def test_disclosure_clamps_to_phi(self):
        """Hard constraint: disclosed_value <= Phi."""
        invention = _make_invention(self_assessed_value=0.8)
        llm = MagicMock(spec=LLMClient)
        llm.create_message.return_value = _mock_tool_response(
            "make_disclosure",
            {
                "summary": "Great invention",
                "technical_details": "Details",
                "disclosed_value": 0.8,
                "withheld_aspects": [],
                "reasoning": "Full disclosure",
            },
        )
        llm.extract_tool_use.return_value = {
            "name": "make_disclosure",
            "input": {
                "summary": "Great invention",
                "technical_details": "Details",
                "disclosed_value": 0.8,
                "withheld_aspects": [],
                "reasoning": "Full disclosure",
            },
            "id": "mock_id",
        }

        agent = SellerAgent(invention, llm, security_threshold=0.5)  # Phi = 0.5
        msg = agent.decide_disclosure()

        assert msg.disclosure is not None
        assert msg.disclosure.disclosed_value <= 0.5  # Clamped to Phi

    def test_rejects_below_floor(self):
        """Hard constraint: reject price below alpha_0 * omega_hat."""
        invention = _make_invention(self_assessed_value=0.75, outside_option_value=0.3)
        llm = MagicMock(spec=LLMClient)
        agent = SellerAgent(invention, llm, security_threshold=1.0)
        # Simulate disclosure so omega_hat is set
        agent.disclosed_omega_hat = 0.75

        # floor = alpha_0 * omega_hat = 0.3 * 0.75 = 0.225
        msg = agent.evaluate_offer(0.1, "Low offer", round_num=1)

        assert msg.price_proposal is not None
        assert msg.price_proposal.proposed_price >= agent.acceptance_floor

    def test_fallback_disclosure(self):
        """When LLM fails, fallback produces valid disclosure."""
        invention = _make_invention(self_assessed_value=0.75)
        llm = MagicMock(spec=LLMClient)
        llm.create_message.return_value = MagicMock(content=[])
        llm.extract_tool_use.return_value = None

        agent = SellerAgent(invention, llm, security_threshold=1.0)
        msg = agent.decide_disclosure()

        assert msg.disclosure is not None
        assert msg.disclosure.disclosed_value <= invention.self_assessed_value
        assert msg.role == AgentRole.SELLER


class TestBuyerAgent:
    def test_offer_clamps_to_budget(self):
        """Hard constraint: price <= budget_cap."""
        llm = MagicMock(spec=LLMClient)

        # Evaluation response
        eval_resp = _mock_tool_response(
            "evaluate_invention",
            {
                "assessed_value": 0.9,
                "strengths": ["Good"],
                "concerns": [],
                "reasoning": "High value",
            },
        )
        # Offer response with price exceeding budget
        offer_resp = _mock_tool_response(
            "make_offer",
            {
                "price": 0.8,  # Exceeds budget of 0.3
                "explanation": "Worth it",
                "private_reasoning": "Overpaying",
            },
        )

        llm.create_message.side_effect = [eval_resp, offer_resp]
        llm.extract_tool_use.side_effect = [
            {
                "name": "evaluate_invention",
                "input": {
                    "assessed_value": 0.9,
                    "strengths": ["Good"],
                    "concerns": [],
                    "reasoning": "High value",
                },
                "id": "eval_id",
            },
            {
                "name": "make_offer",
                "input": {
                    "price": 0.8,
                    "explanation": "Worth it",
                    "private_reasoning": "Overpaying",
                },
                "id": "offer_id",
            },
        ]

        agent = BuyerAgent(budget_cap=0.3, theta=0.65, llm_client=llm)
        disclosure = InventionDisclosure(
            summary="Test", technical_details="Details",
            disclosed_value=0.7, disclosure_fraction=0.9,
            withheld_aspects=[],
        )
        msg = agent.evaluate_disclosure(disclosure)

        assert msg.price_proposal is not None
        assert msg.price_proposal.proposed_price <= 0.3  # Clamped to budget

    def test_fallback_offer(self):
        """When LLM fails, fallback produces valid offer."""
        llm = MagicMock(spec=LLMClient)
        # Both calls return no tool use
        no_tool_resp = MagicMock(content=[])
        llm.create_message.side_effect = [no_tool_resp, no_tool_resp]
        llm.extract_tool_use.return_value = None

        agent = BuyerAgent(budget_cap=0.5, theta=0.65, llm_client=llm)
        disclosure = InventionDisclosure(
            summary="Test", technical_details="Details",
            disclosed_value=0.6, disclosure_fraction=0.8,
            withheld_aspects=[],
        )
        msg = agent.evaluate_disclosure(disclosure)

        assert msg.price_proposal is not None
        assert msg.price_proposal.proposed_price <= 0.5
        assert msg.price_proposal.proposed_price == pytest.approx(0.65 * 0.6, abs=0.01)

    def test_offer_non_negative(self):
        """Offer price is always >= 0."""
        llm = MagicMock(spec=LLMClient)
        eval_resp = _mock_tool_response(
            "evaluate_invention",
            {"assessed_value": 0.1, "strengths": [], "concerns": ["Bad"], "reasoning": "Low"},
        )
        offer_resp = _mock_tool_response(
            "make_offer",
            {"price": -0.5, "explanation": "Worthless", "private_reasoning": "Negative"},
        )
        llm.create_message.side_effect = [eval_resp, offer_resp]
        llm.extract_tool_use.side_effect = [
            {"name": "evaluate_invention", "input": {"assessed_value": 0.1}, "id": "e"},
            {"name": "make_offer", "input": {"price": -0.5, "explanation": "x", "private_reasoning": "y"}, "id": "o"},
        ]

        agent = BuyerAgent(budget_cap=0.5, theta=0.65, llm_client=llm)
        disclosure = InventionDisclosure(
            summary="Test", technical_details="Details",
            disclosed_value=0.6, disclosure_fraction=0.8,
            withheld_aspects=[],
        )
        msg = agent.evaluate_disclosure(disclosure)

        assert msg.price_proposal is not None
        assert msg.price_proposal.proposed_price >= 0
