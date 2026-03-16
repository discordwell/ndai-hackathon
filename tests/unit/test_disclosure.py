"""Tests for disclosure computation."""

import pytest

from ndai.enclave.negotiation.disclosure import (
    compute_disclosure_decision,
    validate_disclosure,
)
from ndai.enclave.negotiation.engine import SecurityParams


@pytest.fixture
def high_security():
    return SecurityParams(k=3, p=0.005, c=7_500_000_000)


@pytest.fixture
def low_security():
    return SecurityParams(k=2, p=0.001, c=100)


class TestComputeDisclosureDecision:
    def test_full_disclosure_when_within_capacity(self, high_security):
        decision = compute_disclosure_decision(0.5, high_security)
        assert decision.is_full_disclosure
        assert decision.omega_hat == 0.5
        assert decision.disclosure_fraction == pytest.approx(1.0)

    def test_capped_by_security_capacity(self, low_security):
        decision = compute_disclosure_decision(0.99, low_security)
        # Low security => small Phi
        assert decision.omega_hat <= decision.phi
        assert decision.is_capacity_limited

    def test_voluntary_cap(self, high_security):
        decision = compute_disclosure_decision(0.8, high_security, max_disclosure_fraction=0.5)
        assert decision.omega_hat <= 0.8 * 0.5 + 1e-10
        assert decision.disclosure_fraction <= 0.5 + 1e-10

    def test_zero_omega(self, high_security):
        decision = compute_disclosure_decision(0.0, high_security)
        assert decision.omega_hat == 0.0
        assert decision.disclosure_fraction == 0.0


class TestValidateDisclosure:
    def test_valid(self):
        assert validate_disclosure(0.5, 0.8, 1.0) is None

    def test_negative(self):
        assert validate_disclosure(-0.1, 0.8, 1.0) is not None

    def test_exceeds_omega(self):
        assert validate_disclosure(0.9, 0.8, 1.0) is not None

    def test_exceeds_phi(self):
        assert validate_disclosure(0.6, 0.8, 0.5) is not None
