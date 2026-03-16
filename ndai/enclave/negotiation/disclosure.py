"""Disclosure computation and validation.

Manages the seller's disclosure decision: what fraction of the invention
to reveal, subject to security capacity constraints.
"""

from dataclasses import dataclass

from ndai.enclave.negotiation.engine import SecurityParams, security_capacity


@dataclass(frozen=True)
class DisclosureDecision:
    """Result of a disclosure computation."""

    omega: float  # True value
    omega_hat: float  # Disclosed value
    phi: float  # Security capacity
    disclosure_fraction: float  # omega_hat / omega
    is_full_disclosure: bool  # omega_hat == omega
    is_capacity_limited: bool  # omega > phi


def compute_disclosure_decision(
    omega: float,
    security_params: SecurityParams,
    max_disclosure_fraction: float = 1.0,
) -> DisclosureDecision:
    """Compute the disclosure decision with all constraints.

    Args:
        omega: Seller's true value assessment.
        security_params: TEE security parameters for Phi computation.
        max_disclosure_fraction: Seller's voluntary cap on disclosure (0, 1].

    Returns:
        DisclosureDecision with all computed values.
    """
    phi = security_capacity(security_params)

    # Apply security capacity constraint
    omega_hat = min(omega, phi)

    # Apply voluntary disclosure cap
    voluntary_cap = omega * max_disclosure_fraction
    omega_hat = min(omega_hat, voluntary_cap)

    fraction = omega_hat / omega if omega > 0 else 0.0

    return DisclosureDecision(
        omega=omega,
        omega_hat=omega_hat,
        phi=phi,
        disclosure_fraction=fraction,
        is_full_disclosure=abs(omega_hat - omega) < 1e-10,
        is_capacity_limited=omega > phi,
    )


def validate_disclosure(omega_hat: float, omega: float, phi: float) -> str | None:
    """Validate a disclosure value. Returns error message or None if valid."""
    if omega_hat < 0:
        return "Disclosure cannot be negative"
    if omega_hat > omega + 1e-10:
        return f"Disclosure {omega_hat} exceeds true value {omega}"
    if omega_hat > phi + 1e-10:
        return f"Disclosure {omega_hat} exceeds security capacity {phi}"
    return None
