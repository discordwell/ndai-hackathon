"""Shelf-life decay model for zero-day vulnerability valuation.

Zero-days have time-decaying value unlike inventions. This module provides
the mathematical foundation replacing the static Phi in engine.py.

    V(t) = V_0 * exp(-lambda * t) * (1 - P_patch(t)) * exclusivity_premium

All functions are pure — no side effects, no I/O.
"""

import math
from dataclasses import dataclass
from enum import Enum


class VulnOutcomeType(Enum):
    AGREEMENT = "agreement"
    NO_DEAL = "no_deal"
    ERROR = "error"


# Lambda values by software category (patches per day, empirically estimated)
DECAY_RATES: dict[str, float] = {
    "browser": 0.015,  # Fast patch cadence (Chrome, Firefox)
    "os_kernel": 0.005,  # Moderate (Linux, Windows kernel)
    "web_server": 0.008,  # Moderate (Apache, Nginx)
    "enterprise": 0.003,  # Slow (Oracle, SAP)
    "embedded": 0.001,  # Very slow (IoT, firmware)
    "mobile": 0.010,  # Moderate-fast (iOS, Android)
    "default": 0.007,
}


@dataclass(frozen=True)
class ShelfLifeParams:
    """Parameters for the vulnerability decay model."""

    v_0: float  # Initial value at discovery [0, 1]
    lambda_rate: float  # Natural decay rate
    days_since_discovery: float  # Time elapsed
    patch_probability: float  # P_patch(t) in [0, 1)
    exclusivity_premium: float = 1.0  # 1.0 for non-exclusive, up to 1.5 for exclusive

    def __post_init__(self):
        if not 0 <= self.v_0 <= 1:
            raise ValueError("v_0 must be in [0, 1]")
        if self.lambda_rate < 0:
            raise ValueError("lambda_rate must be non-negative")
        if self.days_since_discovery < 0:
            raise ValueError("days_since_discovery must be non-negative")
        if not 0 <= self.patch_probability < 1:
            raise ValueError("patch_probability must be in [0, 1)")
        if self.exclusivity_premium < 1.0:
            raise ValueError("exclusivity_premium must be >= 1.0")


@dataclass(frozen=True)
class VulnNegotiationParams:
    """Full parameters for a vulnerability negotiation."""

    shelf_life: ShelfLifeParams
    alpha_0: float  # Seller's outside option multiplier in (0, 1]
    budget_cap: float  # Buyer's maximum payment
    disclosure_level: int = 0  # 0-3, decided by seller agent
    max_disclosure_level: int = 3  # Seller's cap

    def __post_init__(self):
        if not 0 < self.alpha_0 <= 1:
            raise ValueError("alpha_0 must be in (0, 1]")
        if self.budget_cap < 0:
            raise ValueError("budget_cap must be non-negative")
        if not 0 <= self.disclosure_level <= 3:
            raise ValueError("disclosure_level must be in [0, 3]")
        if not 0 <= self.max_disclosure_level <= 3:
            raise ValueError("max_disclosure_level must be in [0, 3]")


@dataclass(frozen=True)
class VulnNegotiationResult:
    """Outcome of a vulnerability negotiation."""

    outcome: VulnOutcomeType
    final_price: float | None
    current_value: float  # V(t) at negotiation time
    disclosure_level: int
    disclosure_fraction: float  # level / 3.0
    seller_payoff: float | None
    buyer_payoff: float | None
    buyer_valuation: float | None = None
    negotiation_rounds: int = 1
    reason: str = ""


def compute_current_value(params: ShelfLifeParams) -> float:
    """Compute time-decayed vulnerability value.

    V(t) = V_0 * exp(-lambda * t) * (1 - P_patch(t)) * exclusivity_premium

    Components:
    - exp(-lambda * t): natural value decay over time
    - (1 - P_patch(t)): survival factor (prob vuln is still unpatched)
    - exclusivity_premium: multiplier for exclusive deals
    """
    decay = math.exp(-params.lambda_rate * params.days_since_discovery)
    survival = 1 - params.patch_probability
    return params.v_0 * decay * survival * params.exclusivity_premium


def estimate_patch_probability(days: float, category: str = "default") -> float:
    """Estimate probability of independent patch by time t.

    Simple exponential CDF model: P(t) = 1 - exp(-mu * t)
    where mu is derived from category patch cadence (half the decay rate).
    """
    mu = DECAY_RATES.get(category, DECAY_RATES["default"]) * 0.5
    return 1 - math.exp(-mu * days)


def get_decay_rate(category: str) -> float:
    """Look up the decay rate for a software category."""
    return DECAY_RATES.get(category, DECAY_RATES["default"])


def disclosure_to_fraction(level: int) -> float:
    """Convert discrete disclosure level (0-3) to normalized fraction [0, 1]."""
    return min(max(level, 0), 3) / 3.0


def compute_vuln_theta(alpha_0: float) -> float:
    """Nash bargaining parameter, same as invention case.

    theta = (1 + alpha_0) / 2
    """
    return (1 + alpha_0) / 2


def compute_vuln_bilateral_price(
    alpha_0: float, omega_hat: float, buyer_valuation: float
) -> float:
    """Bilateral Nash bargaining price for vulnerability deals.

    P* = (v_b + alpha_0 * omega_hat) / 2

    Derived by maximizing Nash product (P - alpha_0*omega_hat)(v_b - P).
    """
    return (buyer_valuation + alpha_0 * omega_hat) / 2


def check_vuln_deal_viability(
    buyer_valuation: float, alpha_0: float, omega_hat: float
) -> bool:
    """Check whether a vulnerability deal has non-negative surplus.

    Deal is viable when v_b >= alpha_0 * omega_hat.
    """
    return buyer_valuation >= alpha_0 * omega_hat - 1e-10


def resolve_vuln_negotiation(
    params: VulnNegotiationParams, buyer_valuation: float
) -> VulnNegotiationResult:
    """Full resolution of a vulnerability negotiation.

    Steps:
    1. Compute current_value via shelf-life decay
    2. Compute omega_hat = current_value * disclosure_fraction
    3. Check deal viability: v_b >= alpha_0 * omega_hat
    4. Compute bilateral Nash price: P* = (v_b + alpha_0 * omega_hat) / 2
    5. Check budget cap
    6. Compute payoffs
    """
    current_value = compute_current_value(params.shelf_life)
    effective_level = min(params.disclosure_level, params.max_disclosure_level)
    disclosure_fraction = disclosure_to_fraction(effective_level)
    omega_hat = current_value * disclosure_fraction

    # Check deal viability
    if not check_vuln_deal_viability(buyer_valuation, params.alpha_0, omega_hat):
        return VulnNegotiationResult(
            outcome=VulnOutcomeType.NO_DEAL,
            final_price=None,
            current_value=current_value,
            disclosure_level=effective_level,
            disclosure_fraction=disclosure_fraction,
            seller_payoff=None,
            buyer_payoff=None,
            buyer_valuation=buyer_valuation,
            reason=(
                f"No surplus: buyer valuation {buyer_valuation:.4f} "
                f"< seller floor {params.alpha_0 * omega_hat:.4f}"
            ),
        )

    price = compute_vuln_bilateral_price(params.alpha_0, omega_hat, buyer_valuation)

    # Check budget cap
    if price > params.budget_cap:
        return VulnNegotiationResult(
            outcome=VulnOutcomeType.NO_DEAL,
            final_price=None,
            current_value=current_value,
            disclosure_level=effective_level,
            disclosure_fraction=disclosure_fraction,
            seller_payoff=None,
            buyer_payoff=None,
            buyer_valuation=buyer_valuation,
            reason=f"Price {price:.4f} exceeds budget {params.budget_cap:.4f}",
        )

    # Compute payoffs
    seller_payoff = price + params.alpha_0 * (current_value - omega_hat)
    buyer_payoff = buyer_valuation - price

    return VulnNegotiationResult(
        outcome=VulnOutcomeType.AGREEMENT,
        final_price=price,
        current_value=current_value,
        disclosure_level=effective_level,
        disclosure_fraction=disclosure_fraction,
        seller_payoff=seller_payoff,
        buyer_payoff=buyer_payoff,
        buyer_valuation=buyer_valuation,
        reason="Bilateral Nash bargaining equilibrium reached",
    )


def compute_decay_numerator(params: ShelfLifeParams) -> int:
    """Compute decay factor as integer numerator with 1e18 denominator.

    Used for on-chain price adjustment in VulnEscrow.sol:
        decayAdjustedPrice = (finalPrice * decayNumerator) / 1e18
    """
    decay = math.exp(-params.lambda_rate * params.days_since_discovery)
    survival = 1 - params.patch_probability
    factor = decay * survival * params.exclusivity_premium
    return int(factor * 10**18)
