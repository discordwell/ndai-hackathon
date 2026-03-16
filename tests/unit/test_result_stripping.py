"""Tests for result stripping / leakage prevention (Phase 6b-B)."""

import pytest

from ndai.enclave.app import _sanitize_reason, _strip_sensitive_fields


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
            "reason": "Bilateral Nash bargaining equilibrium reached",
        }
        stripped = _strip_sensitive_fields(full_result)

        assert stripped == {
            "outcome": "agreement",
            "final_price": 0.45,
            "reason": "Agreement reached",
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

    def test_reason_sanitized_when_present(self):
        result = {"outcome": "no_deal", "final_price": None, "reason": "Price 0.500000 exceeds budget cap 0.400000"}
        stripped = _strip_sensitive_fields(result)
        assert stripped["reason"] == "Exceeds budget"

    def test_no_deal_result(self):
        result = {
            "outcome": "no_deal",
            "final_price": None,
            "omega_hat": 0.5,
            "theta": 0.65,
            "phi": 100.0,
            "seller_payoff": None,
            "buyer_payoff": None,
            "reason": "No surplus: buyer valuation 0.3000 < seller reservation 0.2100",
        }
        stripped = _strip_sensitive_fields(result)
        assert stripped == {
            "outcome": "no_deal",
            "final_price": None,
            "reason": "No deal",
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
            # Unknown reasons get generic text to prevent leakage
            "reason": "Negotiation concluded",
        }

    def test_empty_result(self):
        stripped = _strip_sensitive_fields({})
        assert stripped == {}

    def test_unknown_fields_stripped(self):
        result = {
            "outcome": "agreement",
            "final_price": 0.5,
            "reason": "Bilateral Nash bargaining equilibrium reached",
            "secret_internal_state": "should not leak",
            "debug_info": {"sensitive": True},
        }
        stripped = _strip_sensitive_fields(result)
        assert "secret_internal_state" not in stripped
        assert "debug_info" not in stripped
        assert len(stripped) == 3


class TestSanitizeReason:
    """Tests for _sanitize_reason() — prevent numerical leakage via reason strings."""

    def test_none_passthrough(self):
        assert _sanitize_reason(None) is None

    def test_bilateral_nash_sanitized(self):
        assert _sanitize_reason("Bilateral Nash bargaining equilibrium reached") == "Agreement reached"

    def test_nash_sanitized(self):
        assert _sanitize_reason("Nash bargaining equilibrium reached") == "Agreement reached"

    def test_buyer_valuation_leak_caught(self):
        reason = "No surplus: buyer valuation 0.3000 < seller reservation 0.2100"
        assert _sanitize_reason(reason) == "No deal"

    def test_budget_exceeded_leak_caught(self):
        reason = "Price 0.500000 exceeds budget cap 0.400000"
        assert _sanitize_reason(reason) == "Exceeds budget"

    def test_below_threshold_leak_caught(self):
        reason = "Price 0.100000 below seller threshold 0.210000"
        assert _sanitize_reason(reason) == "Below seller threshold"

    def test_unknown_reason_gets_generic(self):
        assert _sanitize_reason("Some unexpected internal state info") == "Negotiation concluded"

    def test_no_numerical_values_in_sanitized_output(self):
        """No matter what the input, output should not contain float patterns."""
        import re
        float_re = re.compile(r"\d+\.\d{3,}")  # 3+ decimal places (like 0.3000)
        reasons = [
            "No surplus: buyer valuation 0.3000 < seller reservation 0.2100",
            "Price 0.500000 exceeds budget cap 0.400000",
            "Price 0.100000 below seller threshold 0.210000",
            "Bilateral Nash bargaining equilibrium reached",
        ]
        for reason in reasons:
            sanitized = _sanitize_reason(reason)
            assert not float_re.search(sanitized), f"Numerical leak in: {sanitized}"
