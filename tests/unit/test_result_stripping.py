"""Tests for result stripping / leakage prevention (Phase 6b-B)."""

import pytest

from ndai.enclave.app import _strip_sensitive_fields


class TestStripSensitiveFields:
    """Tests for _strip_sensitive_fields()."""

    def test_full_result_stripped_to_safe_fields(self):
        full_result = {
            "outcome": "agreement",
            "final_price": 0.45,
            "omega_hat": 0.6,
            "theta": 0.65,
            "phi": 100.0,
            "seller_payoff": 0.5,
            "buyer_payoff": 0.15,
            "buyer_valuation": 0.6,
            "reason": "Nash bargaining equilibrium reached",
        }
        stripped = _strip_sensitive_fields(full_result)

        assert stripped == {
            "outcome": "agreement",
            "final_price": 0.45,
            "reason": "Nash bargaining equilibrium reached",
        }

    def test_no_omega_hat_survives(self):
        result = {"outcome": "agreement", "omega_hat": 0.7, "final_price": 0.3}
        stripped = _strip_sensitive_fields(result)
        assert "omega_hat" not in stripped

    def test_no_buyer_valuation_survives(self):
        result = {"outcome": "agreement", "buyer_valuation": 0.8, "final_price": 0.4}
        stripped = _strip_sensitive_fields(result)
        assert "buyer_valuation" not in stripped

    def test_no_payoffs_survive(self):
        result = {
            "outcome": "agreement",
            "final_price": 0.5,
            "seller_payoff": 0.6,
            "buyer_payoff": 0.2,
        }
        stripped = _strip_sensitive_fields(result)
        assert "seller_payoff" not in stripped
        assert "buyer_payoff" not in stripped

    def test_no_theta_phi_survive(self):
        result = {
            "outcome": "no_deal",
            "final_price": None,
            "theta": 0.65,
            "phi": 100.0,
        }
        stripped = _strip_sensitive_fields(result)
        assert "theta" not in stripped
        assert "phi" not in stripped

    def test_reason_included_when_present(self):
        result = {"outcome": "no_deal", "final_price": None, "reason": "Budget exceeded"}
        stripped = _strip_sensitive_fields(result)
        assert stripped["reason"] == "Budget exceeded"

    def test_no_deal_result(self):
        result = {
            "outcome": "no_deal",
            "final_price": None,
            "omega_hat": 0.5,
            "theta": 0.65,
            "phi": 100.0,
            "seller_payoff": None,
            "buyer_payoff": None,
            "reason": "Budget exceeded",
        }
        stripped = _strip_sensitive_fields(result)
        assert stripped == {
            "outcome": "no_deal",
            "final_price": None,
            "reason": "Budget exceeded",
        }

    def test_error_result(self):
        result = {
            "outcome": "error",
            "final_price": None,
            "omega_hat": 0.0,
            "theta": 0.0,
            "phi": 0.0,
            "seller_payoff": None,
            "buyer_payoff": None,
            "reason": "LLM exploded",
        }
        stripped = _strip_sensitive_fields(result)
        assert stripped == {
            "outcome": "error",
            "final_price": None,
            "reason": "LLM exploded",
        }

    def test_empty_result(self):
        stripped = _strip_sensitive_fields({})
        assert stripped == {}

    def test_unknown_fields_stripped(self):
        result = {
            "outcome": "agreement",
            "final_price": 0.5,
            "reason": "Deal",
            "secret_internal_state": "should not leak",
            "debug_info": {"sensitive": True},
        }
        stripped = _strip_sensitive_fields(result)
        assert "secret_internal_state" not in stripped
        assert "debug_info" not in stripped
        assert len(stripped) == 3
