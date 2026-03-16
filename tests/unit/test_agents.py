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
    def test_assessed_value_extracted(self):
        """Buyer agent extracts assessed_value from evaluation."""
        llm = MagicMock(spec=LLMClient)
        eval_resp = _mock_tool_response(
            "evaluate_invention",
            {
                "assessed_value": 0.65,
                "strengths": ["Good"],
                "concerns": [],
                "reasoning": "Fair value",
            },
        )
        llm.create_message.return_value = eval_resp
        llm.extract_tool_use.return_value = {
            "name": "evaluate_invention",
            "input": {
                "assessed_value": 0.65,
                "strengths": ["Good"],
                "concerns": [],
                "reasoning": "Fair value",
            },
            "id": "eval_id",
        }

        agent = BuyerAgent(budget_cap=0.5, theta=0.65, llm_client=llm)
        disclosure = InventionDisclosure(
            summary="Test", technical_details="Details",
            disclosed_value=0.7, disclosure_fraction=0.9,
            withheld_aspects=[],
        )
        agent.evaluate_disclosure(disclosure)

        assert agent.assessed_value == pytest.approx(0.65)

    def test_assessed_value_clamped(self):
        """Hard constraint: assessed_value clamped to [0, 1]."""
        llm = MagicMock(spec=LLMClient)
        eval_resp = _mock_tool_response(
            "evaluate_invention",
            {
                "assessed_value": 1.5,  # Exceeds 1.0
                "strengths": ["Great"],
                "concerns": [],
                "reasoning": "Overvalued",
            },
        )
        llm.create_message.return_value = eval_resp
        llm.extract_tool_use.return_value = {
            "name": "evaluate_invention",
            "input": {
                "assessed_value": 1.5,
                "strengths": ["Great"],
                "concerns": [],
                "reasoning": "Overvalued",
            },
            "id": "eval_id",
        }

        agent = BuyerAgent(budget_cap=0.5, theta=0.65, llm_client=llm)
        disclosure = InventionDisclosure(
            summary="Test", technical_details="Details",
            disclosed_value=0.7, disclosure_fraction=0.9,
            withheld_aspects=[],
        )
        agent.evaluate_disclosure(disclosure)

        assert agent.assessed_value <= 1.0

    def test_assessed_value_clamped_negative(self):
        """assessed_value clamped to >= 0."""
        llm = MagicMock(spec=LLMClient)
        eval_resp = _mock_tool_response(
            "evaluate_invention",
            {"assessed_value": -0.5, "strengths": [], "concerns": ["Bad"], "reasoning": "Low"},
        )
        llm.create_message.return_value = eval_resp
        llm.extract_tool_use.return_value = {
            "name": "evaluate_invention",
            "input": {"assessed_value": -0.5, "strengths": [], "concerns": ["Bad"], "reasoning": "Low"},
            "id": "e",
        }

        agent = BuyerAgent(budget_cap=0.5, theta=0.65, llm_client=llm)
        disclosure = InventionDisclosure(
            summary="Test", technical_details="Details",
            disclosed_value=0.6, disclosure_fraction=0.8,
            withheld_aspects=[],
        )
        agent.evaluate_disclosure(disclosure)

        assert agent.assessed_value >= 0

    def test_fallback_evaluation(self):
        """When LLM fails, fallback sets assessed_value to omega_hat."""
        llm = MagicMock(spec=LLMClient)
        no_tool_resp = MagicMock(content=[])
        llm.create_message.return_value = no_tool_resp
        llm.extract_tool_use.return_value = None

        agent = BuyerAgent(budget_cap=0.5, theta=0.65, llm_client=llm)
        disclosure = InventionDisclosure(
            summary="Test", technical_details="Details",
            disclosed_value=0.6, disclosure_fraction=0.8,
            withheld_aspects=[],
        )
        agent.evaluate_disclosure(disclosure)

        assert agent.assessed_value == pytest.approx(0.6)  # Defaults to omega_hat
