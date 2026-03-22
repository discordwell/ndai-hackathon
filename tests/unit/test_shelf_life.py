"""Tests for the shelf-life decay model for zero-day vulnerability valuation."""

import math

import pytest

from ndai.enclave.negotiation.shelf_life import (
    DECAY_RATES,
    ShelfLifeParams,
    VulnNegotiationParams,
    VulnNegotiationResult,
    VulnOutcomeType,
    check_vuln_deal_viability,
    compute_current_value,
    compute_decay_numerator,
    compute_vuln_bilateral_price,
    disclosure_to_fraction,
    estimate_patch_probability,
    get_decay_rate,
    resolve_vuln_negotiation,
)


class TestShelfLifeParams:
    def test_valid_construction(self):
        params = ShelfLifeParams(v_0=0.8, lambda_rate=0.01, days_since_discovery=30, patch_probability=0.1)
        assert params.v_0 == 0.8
        assert params.exclusivity_premium == 1.0

    def test_invalid_v_0(self):
        with pytest.raises(ValueError, match="v_0"):
            ShelfLifeParams(v_0=1.5, lambda_rate=0.01, days_since_discovery=0, patch_probability=0)

    def test_invalid_lambda_negative(self):
        with pytest.raises(ValueError, match="lambda_rate"):
            ShelfLifeParams(v_0=0.5, lambda_rate=-0.01, days_since_discovery=0, patch_probability=0)

    def test_invalid_days_negative(self):
        with pytest.raises(ValueError, match="days_since_discovery"):
            ShelfLifeParams(v_0=0.5, lambda_rate=0.01, days_since_discovery=-1, patch_probability=0)

    def test_invalid_patch_prob(self):
        with pytest.raises(ValueError, match="patch_probability"):
            ShelfLifeParams(v_0=0.5, lambda_rate=0.01, days_since_discovery=0, patch_probability=1.0)

    def test_invalid_exclusivity_premium(self):
        with pytest.raises(ValueError, match="exclusivity_premium"):
            ShelfLifeParams(v_0=0.5, lambda_rate=0.01, days_since_discovery=0, patch_probability=0, exclusivity_premium=0.5)


class TestComputeCurrentValue:
    def test_zero_days_no_decay(self):
        """At discovery time, value equals v_0."""
        params = ShelfLifeParams(v_0=0.9, lambda_rate=0.01, days_since_discovery=0, patch_probability=0)
        assert compute_current_value(params) == pytest.approx(0.9)

    def test_value_decays_over_time(self):
        fresh = ShelfLifeParams(v_0=0.9, lambda_rate=0.01, days_since_discovery=0, patch_probability=0)
        aged = ShelfLifeParams(v_0=0.9, lambda_rate=0.01, days_since_discovery=90, patch_probability=0)
        assert compute_current_value(aged) < compute_current_value(fresh)

    def test_higher_patch_prob_lowers_value(self):
        low = ShelfLifeParams(v_0=0.9, lambda_rate=0.01, days_since_discovery=30, patch_probability=0.1)
        high = ShelfLifeParams(v_0=0.9, lambda_rate=0.01, days_since_discovery=30, patch_probability=0.5)
        assert compute_current_value(high) < compute_current_value(low)

    def test_exclusivity_premium_increases_value(self):
        base = ShelfLifeParams(v_0=0.8, lambda_rate=0.01, days_since_discovery=10, patch_probability=0.05)
        excl = ShelfLifeParams(v_0=0.8, lambda_rate=0.01, days_since_discovery=10, patch_probability=0.05, exclusivity_premium=1.3)
        assert compute_current_value(excl) > compute_current_value(base)

    def test_exponential_decay_formula(self):
        params = ShelfLifeParams(v_0=1.0, lambda_rate=0.01, days_since_discovery=100, patch_probability=0)
        expected = math.exp(-0.01 * 100)
        assert compute_current_value(params) == pytest.approx(expected)

    def test_max_decay_near_zero(self):
        """Very old vulnerability with high patch probability should be near zero."""
        params = ShelfLifeParams(v_0=0.9, lambda_rate=0.015, days_since_discovery=365, patch_probability=0.95)
        assert compute_current_value(params) < 0.01


class TestEstimatePatchProbability:
    def test_zero_days(self):
        assert estimate_patch_probability(0) == pytest.approx(0.0)

    def test_increases_over_time(self):
        p30 = estimate_patch_probability(30, "browser")
        p180 = estimate_patch_probability(180, "browser")
        assert p180 > p30

    def test_browser_faster_than_embedded(self):
        p_browser = estimate_patch_probability(90, "browser")
        p_embedded = estimate_patch_probability(90, "embedded")
        assert p_browser > p_embedded


class TestDisclosureToFraction:
    def test_levels(self):
        assert disclosure_to_fraction(0) == pytest.approx(0.0)
        assert disclosure_to_fraction(1) == pytest.approx(1 / 3)
        assert disclosure_to_fraction(2) == pytest.approx(2 / 3)
        assert disclosure_to_fraction(3) == pytest.approx(1.0)

    def test_clamp_negative(self):
        assert disclosure_to_fraction(-1) == pytest.approx(0.0)

    def test_clamp_over(self):
        assert disclosure_to_fraction(5) == pytest.approx(1.0)


class TestBilateralPrice:
    def test_formula(self):
        price = compute_vuln_bilateral_price(alpha_0=0.3, omega_hat=0.5, buyer_valuation=0.6)
        expected = (0.6 + 0.3 * 0.5) / 2
        assert price == pytest.approx(expected)


class TestDealViability:
    def test_viable(self):
        assert check_vuln_deal_viability(0.5, 0.3, 0.5) is True

    def test_not_viable(self):
        assert check_vuln_deal_viability(0.01, 0.3, 0.5) is False


class TestResolveVulnNegotiation:
    def _make_params(self, days=10, level=2, budget=1.0):
        shelf = ShelfLifeParams(v_0=0.8, lambda_rate=0.007, days_since_discovery=days, patch_probability=0.05)
        return VulnNegotiationParams(shelf_life=shelf, alpha_0=0.3, budget_cap=budget, disclosure_level=level)

    def test_agreement(self):
        params = self._make_params()
        result = resolve_vuln_negotiation(params, buyer_valuation=0.7)
        assert result.outcome == VulnOutcomeType.AGREEMENT
        assert result.final_price is not None
        assert result.final_price > 0

    def test_no_deal_low_valuation(self):
        params = self._make_params()
        result = resolve_vuln_negotiation(params, buyer_valuation=0.001)
        assert result.outcome == VulnOutcomeType.NO_DEAL

    def test_no_deal_budget_exceeded(self):
        params = self._make_params(budget=0.001)
        result = resolve_vuln_negotiation(params, buyer_valuation=0.7)
        assert result.outcome == VulnOutcomeType.NO_DEAL
        assert "budget" in result.reason.lower()

    def test_higher_disclosure_higher_omega_hat(self):
        low = self._make_params(level=1)
        high = self._make_params(level=3)
        r_low = resolve_vuln_negotiation(low, buyer_valuation=0.5)
        r_high = resolve_vuln_negotiation(high, buyer_valuation=0.5)
        assert r_high.disclosure_fraction > r_low.disclosure_fraction

    def test_payoffs_consistent(self):
        params = self._make_params()
        result = resolve_vuln_negotiation(params, buyer_valuation=0.6)
        if result.outcome == VulnOutcomeType.AGREEMENT:
            assert result.buyer_payoff == pytest.approx(result.buyer_valuation - result.final_price)


class TestDecayNumerator:
    def test_no_decay(self):
        params = ShelfLifeParams(v_0=1.0, lambda_rate=0.0, days_since_discovery=0, patch_probability=0)
        assert compute_decay_numerator(params) == 10**18

    def test_partial_decay(self):
        params = ShelfLifeParams(v_0=1.0, lambda_rate=0.01, days_since_discovery=100, patch_probability=0)
        num = compute_decay_numerator(params)
        assert 0 < num < 10**18


class TestGetDecayRate:
    def test_known_category(self):
        assert get_decay_rate("browser") == DECAY_RATES["browser"]

    def test_unknown_falls_back(self):
        assert get_decay_rate("unknown_thing") == DECAY_RATES["default"]
