"""Tests for VulnSellerAgent and VulnBuyerAgent with mocked LLM."""

from unittest.mock import MagicMock

import pytest

from ndai.enclave.agents.base_agent import (
    AgentRole,
    VulnDisclosure,
    VulnerabilitySubmission,
)
from ndai.enclave.agents.vuln_buyer_agent import VulnBuyerAgent
from ndai.enclave.agents.vuln_seller_agent import VulnSellerAgent


def _make_vuln(**overrides):
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
        outside_option_value=0.3,
        max_disclosure_level=3,
    )
    defaults.update(overrides)
    return VulnerabilitySubmission(**defaults)


def _mock_llm_disclosure(level=2, tool_id="test-id"):
    """Create a mock LLM that returns a make_vuln_disclosure tool call."""
    mock = MagicMock()
    mock.extract_tool_use.return_value = {
        "name": "make_vuln_disclosure",
        "id": tool_id,
        "input": {
            "disclosure_level": level,
            "affected_component": "mod_proxy",
            "attack_surface": "HTTP request handling",
            "trigger_conditions": "Crafted Content-Length header",
            "constraints": "Requires network access",
            "reasoning": "Level 2 gives enough detail",
        },
    }
    mock.create_message.return_value = MagicMock(content=[])
    return mock


def _mock_llm_evaluation(assessed_value=0.7, tool_id="test-id"):
    """Create a mock LLM that returns an evaluate_vulnerability tool call."""
    mock = MagicMock()
    mock.extract_tool_use.return_value = {
        "name": "evaluate_vulnerability",
        "id": tool_id,
        "input": {
            "assessed_value": assessed_value,
            "cvss_estimate": 8.5,
            "exploitability": "moderate",
            "strengths": ["RCE impact", "popular software"],
            "concerns": ["requires network access"],
            "reasoning": "High severity RCE",
        },
    }
    mock.create_message.return_value = MagicMock(content=[])
    return mock


class TestVulnSellerAgent:
    def test_disclosure_clamps_level(self):
        """Level is clamped to max_disclosure_level."""
        vuln = _make_vuln(max_disclosure_level=1)
        llm = _mock_llm_disclosure(level=3)
        agent = VulnSellerAgent(vuln, llm, current_value=0.8)
        msg = agent.decide_disclosure()
        assert msg.role == AgentRole.VULN_SELLER
        # Level should be clamped to 1
        assert agent.disclosed_level == 1

    def test_disclosure_normal(self):
        vuln = _make_vuln()
        llm = _mock_llm_disclosure(level=2)
        agent = VulnSellerAgent(vuln, llm, current_value=0.8)
        msg = agent.decide_disclosure()
        assert agent.disclosed_level == 2
        assert agent.disclosed_omega_hat is not None

    def test_acceptance_floor(self):
        vuln = _make_vuln(outside_option_value=0.3)
        llm = _mock_llm_disclosure(level=2)
        agent = VulnSellerAgent(vuln, llm, current_value=0.8)
        agent.decide_disclosure()
        # Floor = alpha_0 * omega_hat
        assert agent.acceptance_floor == pytest.approx(0.3 * agent.disclosed_omega_hat)

    def test_reject_below_floor(self):
        vuln = _make_vuln(outside_option_value=0.3)
        llm = _mock_llm_disclosure(level=2)
        agent = VulnSellerAgent(vuln, llm, current_value=0.8)
        agent.decide_disclosure()
        msg = agent.evaluate_offer(0.001, "Low offer", 2)
        # Should counter at floor
        assert msg.price_proposal is not None
        assert msg.price_proposal.proposed_price >= agent.acceptance_floor

    def test_fallback_disclosure(self):
        vuln = _make_vuln()
        llm = MagicMock()
        llm.extract_tool_use.return_value = None
        llm.create_message.return_value = MagicMock(content=[])
        agent = VulnSellerAgent(vuln, llm, current_value=0.8)
        msg = agent.decide_disclosure()
        assert agent.disclosed_level == 1  # Fallback is level 1


class TestVulnBuyerAgent:
    def test_evaluation_clamps_value(self):
        llm = _mock_llm_evaluation(assessed_value=1.5)
        agent = VulnBuyerAgent(budget_cap=1.0, alpha_0=0.3, llm_client=llm)
        disclosure = VulnDisclosure(
            level=2, level_fraction=2 / 3,
            vulnerability_class="CWE-787", impact_type="RCE",
        )
        agent.evaluate_disclosure(disclosure)
        assert agent.assessed_value == 1.0  # Clamped

    def test_evaluation_normal(self):
        llm = _mock_llm_evaluation(assessed_value=0.7)
        agent = VulnBuyerAgent(budget_cap=1.0, alpha_0=0.3, llm_client=llm)
        disclosure = VulnDisclosure(
            level=2, level_fraction=2 / 3,
            vulnerability_class="CWE-787", impact_type="RCE",
        )
        agent.evaluate_disclosure(disclosure)
        assert agent.assessed_value == pytest.approx(0.7)

    def test_fallback_evaluation(self):
        llm = MagicMock()
        llm.extract_tool_use.return_value = None
        llm.create_message.return_value = MagicMock(content=[])
        agent = VulnBuyerAgent(budget_cap=1.0, alpha_0=0.3, llm_client=llm)
        disclosure = VulnDisclosure(
            level=2, level_fraction=2 / 3,
            vulnerability_class="CWE-787", impact_type="RCE",
        )
        agent.evaluate_disclosure(disclosure)
        # Fallback: 50% of disclosure fraction
        assert agent.assessed_value == pytest.approx(2 / 3 * 0.5)

    def test_offer_clamps_price(self):
        """proposed_price should be clamped to budget_cap."""
        llm = MagicMock()
        llm.extract_tool_use.side_effect = [
            # First call: evaluation
            {
                "name": "evaluate_vulnerability", "id": "t1",
                "input": {"assessed_value": 0.7, "cvss_estimate": 8.0, "exploitability": "moderate",
                          "strengths": [], "concerns": [], "reasoning": "ok"},
            },
            # Second call: offer with price > budget
            {
                "name": "make_offer", "id": "t2",
                "input": {"proposed_price": 5.0, "explanation": "High", "reasoning": "test"},
            },
        ]
        llm.create_message.return_value = MagicMock(content=[])
        agent = VulnBuyerAgent(budget_cap=1.0, alpha_0=0.3, llm_client=llm)
        disclosure = VulnDisclosure(level=2, level_fraction=2 / 3,
                                    vulnerability_class="CWE-787", impact_type="RCE")
        agent.evaluate_disclosure(disclosure)
        offer = agent.make_offer(disclosure, round_num=2)
        assert offer is not None
        assert offer.price_proposal.proposed_price <= 1.0
