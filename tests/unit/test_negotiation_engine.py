"""Tests for the NDAI negotiation engine."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    NegotiationParams,
    SecurityParams,
    check_acceptance_threshold,
    check_budget_cap,
    check_deal_viability,
    compute_baseline_payoffs,
    compute_bilateral_price,
    compute_buyer_payoff,
    compute_disclosure,
    compute_equilibrium_price,
    compute_seller_payoff,
    compute_theta,
    resolve_bilateral_negotiation,
    resolve_negotiation,
    security_capacity,
)


class TestSecurityCapacity:
    def test_basic_computation(self):
        # Paper example: k=3, p=0.005, C=7.5B, gamma=1
        params = SecurityParams(k=3, p=0.005, c=7_500_000_000, gamma=1.0)
        phi = security_capacity(params)
        assert phi > 0

    def test_higher_k_increases_phi(self):
        base = SecurityParams(k=2, p=0.01, c=1_000_000)
        higher_k = SecurityParams(k=5, p=0.01, c=1_000_000)
        assert security_capacity(higher_k) > security_capacity(base)

    def test_higher_p_increases_phi(self):
        low_p = SecurityParams(k=3, p=0.001, c=1_000_000)
        high_p = SecurityParams(k=3, p=0.1, c=1_000_000)
        assert security_capacity(high_p) > security_capacity(low_p)

    def test_higher_c_increases_phi(self):
        low_c = SecurityParams(k=3, p=0.01, c=1_000)
        high_c = SecurityParams(k=3, p=0.01, c=1_000_000)
        assert security_capacity(high_c) > security_capacity(low_c)

    def test_gamma_effect(self):
        base = SecurityParams(k=3, p=0.01, c=1_000_000, gamma=1.0)
        high_gamma = SecurityParams(k=3, p=0.01, c=1_000_000, gamma=2.0)
        # Higher gamma amplifies detection, increasing phi
        assert security_capacity(high_gamma) > security_capacity(base)

    def test_invalid_params(self):
        with pytest.raises(ValueError, match="k must be >= 1"):
            SecurityParams(k=0, p=0.01, c=1000)
        with pytest.raises(ValueError, match="p must be in"):
            SecurityParams(k=3, p=0.0, c=1000)
        with pytest.raises(ValueError, match="c must be positive"):
            SecurityParams(k=3, p=0.01, c=-1)


class TestNashBargaining:
    def test_theta_midpoint(self):
        # When alpha_0 = 0.5, theta = 0.75
        assert compute_theta(0.5) == 0.75

    def test_theta_range(self):
        # alpha_0 in (0, 1] => theta in (0.5, 1]
        assert compute_theta(0.01) == pytest.approx(0.505)
        assert compute_theta(1.0) == 1.0

    def test_equilibrium_price(self):
        theta = 0.75
        omega_hat = 0.6
        assert compute_equilibrium_price(theta, omega_hat) == pytest.approx(0.45)

    def test_full_disclosure_price(self):
        # When omega_hat = omega, price = theta * omega
        omega = 0.8
        alpha_0 = 0.3
        theta = compute_theta(alpha_0)
        omega_hat = omega  # Full disclosure
        price = compute_equilibrium_price(theta, omega_hat)
        assert price == pytest.approx(theta * omega)


class TestConstraintChecks:
    def test_budget_cap_within(self):
        assert check_budget_cap(0.5, 0.6) is True

    def test_budget_cap_exact(self):
        assert check_budget_cap(0.5, 0.5) is True

    def test_budget_cap_exceeded(self):
        assert check_budget_cap(0.6, 0.5) is False

    def test_acceptance_threshold_met(self):
        # price=0.5 >= alpha_0*omega_hat = 0.3*0.7 = 0.21
        assert check_acceptance_threshold(0.5, alpha_0=0.3, omega=0.7, omega_hat=0.7) is True

    def test_acceptance_threshold_exact(self):
        alpha_0 = 0.3
        omega_hat = 0.7
        price = alpha_0 * omega_hat  # Exact threshold
        assert check_acceptance_threshold(price, alpha_0=alpha_0, omega=0.8, omega_hat=omega_hat) is True

    def test_acceptance_threshold_not_met(self):
        # price=0.1 < alpha_0*omega_hat = 0.3*0.7 = 0.21
        assert check_acceptance_threshold(0.1, alpha_0=0.3, omega=0.7, omega_hat=0.7) is False


class TestPayoffs:
    def test_seller_payoff_full_disclosure(self):
        # Full disclosure: omega_hat = omega, so second term is 0
        payoff = compute_seller_payoff(price=0.5, alpha_0=0.3, omega=0.8, omega_hat=0.8)
        assert payoff == pytest.approx(0.5)

    def test_seller_payoff_partial_disclosure(self):
        # Partial disclosure: gets price + value from undisclosed portion
        payoff = compute_seller_payoff(price=0.4, alpha_0=0.3, omega=0.8, omega_hat=0.6)
        assert payoff == pytest.approx(0.4 + 0.3 * 0.2)  # 0.46

    def test_buyer_payoff(self):
        payoff = compute_buyer_payoff(omega_hat=0.6, price=0.4)
        assert payoff == pytest.approx(0.2)

    def test_baseline_payoffs(self):
        seller, buyer = compute_baseline_payoffs(omega=0.8, alpha_0=0.3)
        assert seller == pytest.approx(0.24)
        assert buyer == 0.0


class TestResolveNegotiation:
    @pytest.fixture
    def default_security(self):
        return SecurityParams(k=3, p=0.005, c=7_500_000_000)

    def test_successful_agreement(self, default_security):
        params = NegotiationParams(
            omega=0.5,
            alpha_0=0.3,
            budget_cap=1.0,
            security_params=default_security,
        )
        result = resolve_negotiation(params)
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price is not None
        assert result.final_price > 0
        assert result.seller_payoff is not None
        assert result.buyer_payoff is not None

    def test_budget_exceeded(self, default_security):
        params = NegotiationParams(
            omega=0.9,
            alpha_0=0.8,
            budget_cap=0.01,  # Very small budget
            security_params=default_security,
        )
        result = resolve_negotiation(params)
        assert result.outcome == NegotiationOutcomeType.NO_DEAL
        assert "budget cap" in result.reason

    def test_pareto_improvement(self, default_security):
        """Theorem 1: NDAI outcome Pareto-dominates baseline."""
        omega = 0.5
        alpha_0 = 0.3
        params = NegotiationParams(
            omega=omega,
            alpha_0=alpha_0,
            budget_cap=1.0,
            security_params=default_security,
        )
        result = resolve_negotiation(params)
        baseline_seller, baseline_buyer = compute_baseline_payoffs(omega, alpha_0)

        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.seller_payoff is not None
        assert result.buyer_payoff is not None
        assert result.seller_payoff > baseline_seller
        assert result.buyer_payoff > baseline_buyer

    def test_invalid_omega(self, default_security):
        with pytest.raises(ValueError, match="omega must be in"):
            NegotiationParams(
                omega=1.0, alpha_0=0.5, budget_cap=1.0,
                security_params=default_security,
            )

    def test_invalid_alpha_0(self, default_security):
        with pytest.raises(ValueError, match="alpha_0 must be in"):
            NegotiationParams(
                omega=0.5, alpha_0=0.0, budget_cap=1.0,
                security_params=default_security,
            )


class TestPropertyBased:
    @given(
        omega=st.floats(min_value=0.01, max_value=0.99),
        alpha_0=st.floats(min_value=0.01, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_theta_bounds(self, omega, alpha_0):
        theta = compute_theta(alpha_0)
        assert 0.5 < theta <= 1.0

    @given(
        omega=st.floats(min_value=0.01, max_value=0.99),
        alpha_0=st.floats(min_value=0.01, max_value=0.99),
    )
    @settings(max_examples=100)
    def test_pareto_improvement_always_holds(self, omega, alpha_0):
        """Property: When budget is sufficient, NDAI always Pareto-dominates baseline."""
        security = SecurityParams(k=3, p=0.005, c=7_500_000_000)
        params = NegotiationParams(
            omega=omega,
            alpha_0=alpha_0,
            budget_cap=1.0,  # Sufficient budget
            security_params=security,
        )
        result = resolve_negotiation(params)
        baseline_seller, baseline_buyer = compute_baseline_payoffs(omega, alpha_0)

        if result.outcome == NegotiationOutcomeType.AGREEMENT:
            assert result.seller_payoff is not None
            assert result.buyer_payoff is not None
            assert result.seller_payoff >= baseline_seller - 1e-10
            assert result.buyer_payoff >= baseline_buyer - 1e-10

    @given(
        omega=st.floats(min_value=0.01, max_value=0.99),
        alpha_0=st.floats(min_value=0.01, max_value=0.99),
    )
    @settings(max_examples=100)
    def test_price_between_zero_and_omega(self, omega, alpha_0):
        theta = compute_theta(alpha_0)
        omega_hat = omega  # Full disclosure
        price = compute_equilibrium_price(theta, omega_hat)
        assert 0 < price <= omega_hat


class TestBilateralBargaining:
    def test_bilateral_price_basic(self):
        """P* = (v_b + alpha_0 * omega_hat) / 2"""
        price = compute_bilateral_price(alpha_0=0.3, omega_hat=0.7, buyer_valuation=0.65)
        expected = (0.65 + 0.3 * 0.7) / 2  # (0.65 + 0.21) / 2 = 0.43
        assert price == pytest.approx(expected)

    def test_bilateral_backward_compatible(self):
        """When v_b = omega_hat, bilateral price equals theta * omega_hat."""
        alpha_0 = 0.3
        omega_hat = 0.7
        v_b = omega_hat  # Buyer agrees with seller's disclosure

        bilateral = compute_bilateral_price(alpha_0, omega_hat, v_b)
        theta = compute_theta(alpha_0)
        unilateral = compute_equilibrium_price(theta, omega_hat)

        assert bilateral == pytest.approx(unilateral)

    def test_deal_viability_positive(self):
        """v_b >= alpha_0 * omega_hat => viable."""
        assert check_deal_viability(0.5, alpha_0=0.3, omega_hat=0.7) is True

    def test_deal_viability_negative(self):
        """v_b < alpha_0 * omega_hat => not viable."""
        assert check_deal_viability(0.1, alpha_0=0.5, omega_hat=0.8) is False

    def test_deal_viability_exact_boundary(self):
        """Exact boundary: v_b = alpha_0 * omega_hat."""
        assert check_deal_viability(0.21, alpha_0=0.3, omega_hat=0.7) is True

    def test_resolve_bilateral_agreement(self):
        security = SecurityParams(k=3, p=0.005, c=7_500_000_000)
        params = NegotiationParams(
            omega=0.5, alpha_0=0.3, budget_cap=1.0, security_params=security,
        )
        result = resolve_bilateral_negotiation(params, buyer_valuation=0.5)
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price is not None
        assert result.buyer_valuation == 0.5
        assert result.buyer_payoff is not None
        assert result.buyer_payoff == pytest.approx(0.5 - result.final_price)

    def test_resolve_bilateral_no_deal(self):
        security = SecurityParams(k=3, p=0.005, c=7_500_000_000)
        params = NegotiationParams(
            omega=0.5, alpha_0=0.8, budget_cap=1.0, security_params=security,
        )
        # v_b = 0.1 < alpha_0 * omega_hat = 0.8 * 0.5 = 0.4
        result = resolve_bilateral_negotiation(params, buyer_valuation=0.1)
        assert result.outcome == NegotiationOutcomeType.NO_DEAL
        assert "No surplus" in result.reason

    def test_changing_buyer_valuation_changes_price(self):
        """Critical: different buyer valuations produce different prices."""
        security = SecurityParams(k=3, p=0.005, c=7_500_000_000)
        params = NegotiationParams(
            omega=0.5, alpha_0=0.3, budget_cap=1.0, security_params=security,
        )
        result_low = resolve_bilateral_negotiation(params, buyer_valuation=0.3)
        result_high = resolve_bilateral_negotiation(params, buyer_valuation=0.5)

        assert result_low.outcome == NegotiationOutcomeType.AGREEMENT
        assert result_high.outcome == NegotiationOutcomeType.AGREEMENT
        assert result_low.final_price != result_high.final_price
        assert result_high.final_price > result_low.final_price
