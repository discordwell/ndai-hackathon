"""Nash bargaining engine implementing the NDAI mechanism.

Implements the core game-theoretic computations from Stephenson et al. (2025):
- Security capacity Phi (Equation 3)
- Nash bargaining parameter theta
- Equilibrium price P*
- Budget cap and acceptance threshold checks

All functions are pure — no side effects, no I/O.
"""

from dataclasses import dataclass
from enum import Enum


class NegotiationOutcomeType(Enum):
    AGREEMENT = "agreement"
    NO_DEAL = "no_deal"
    ERROR = "error"


@dataclass(frozen=True)
class SecurityParams:
    """Parameters for computing security capacity Phi.

    From Section 3.2 of the paper:
    - k: collusion threshold (number of TEE providers that must collude)
    - p: per-provider breach detection probability
    - c: penalty for detected breach
    - gamma: detection amplification exponent (>= 1, default 1)
    """

    k: int
    p: float
    c: float
    gamma: float = 1.0

    def __post_init__(self):
        if self.k < 1:
            raise ValueError("k must be >= 1")
        if not 0 < self.p < 1:
            raise ValueError("p must be in (0, 1)")
        if self.c <= 0:
            raise ValueError("c must be positive")
        if self.gamma < 1:
            raise ValueError("gamma must be >= 1")


@dataclass(frozen=True)
class NegotiationParams:
    """Parameters for a single NDAI negotiation session."""

    omega: float  # Seller's true value assessment, in [0, 1)
    alpha_0: float  # Seller's outside option multiplier, in (0, 1]
    budget_cap: float  # Buyer's maximum payment P_bar
    security_params: SecurityParams

    def __post_init__(self):
        if not 0 <= self.omega < 1:
            raise ValueError("omega must be in [0, 1)")
        if not 0 < self.alpha_0 <= 1:
            raise ValueError("alpha_0 must be in (0, 1]")
        if self.budget_cap < 0:
            raise ValueError("budget_cap must be non-negative")


@dataclass(frozen=True)
class NegotiationResult:
    """The outcome of an NDAI negotiation."""

    outcome: NegotiationOutcomeType
    final_price: float | None  # P* if agreement, None otherwise
    omega_hat: float  # Disclosed value
    theta: float  # Nash bargaining parameter
    phi: float  # Security capacity
    seller_payoff: float | None  # P + alpha_0 * (omega - omega_hat)
    buyer_payoff: float | None  # v_b - P (buyer's perceived surplus)
    buyer_valuation: float | None = None  # v_b: buyer's independent assessment
    negotiation_rounds: int = 1
    reason: str = ""


def security_capacity(params: SecurityParams) -> float:
    """Compute the maximum securable value Phi.

    From Equation 3 of the paper:
        Phi(k, p, C) = k * (1 - (1-p)^(k^gamma)) * C / (1-p)^(k^gamma)

    This represents the maximum value of an invention that can be
    protected given the security parameters of the TEE infrastructure.
    """
    k_gamma = params.k ** params.gamma
    evasion_prob = (1 - params.p) ** k_gamma
    detection_prob = 1 - evasion_prob

    if evasion_prob == 0:
        return float("inf")

    return params.k * detection_prob / evasion_prob * params.c


def compute_theta(alpha_0: float) -> float:
    """Compute the Nash bargaining parameter theta.

    From the paper's Nash bargaining solution:
        theta = (1 + alpha_0) / 2

    This is the seller's share of the disclosed value.
    """
    return (1 + alpha_0) / 2


def compute_disclosure(omega: float, phi: float) -> float:
    """Compute optimal disclosure level.

    From Section 4: omega_hat = min(omega, Phi)
    The seller discloses up to the security capacity.
    """
    return min(omega, phi)


def compute_equilibrium_price(theta: float, omega_hat: float) -> float:
    """Compute the Nash bargaining equilibrium price.

    P* = theta * omega_hat
    """
    return theta * omega_hat


def check_budget_cap(price: float, budget_cap: float) -> bool:
    """Check whether the price is within the buyer's budget cap.

    Returns True if the price is acceptable (within budget).
    """
    return price <= budget_cap


def check_acceptance_threshold(
    price: float, alpha_0: float, omega: float, omega_hat: float
) -> bool:
    """Check whether the price meets the seller's minimum acceptable price.

    The seller accepts if their total payoff (P + alpha_0 * (omega - omega_hat))
    exceeds their outside option (alpha_0 * omega). This simplifies to:
        P >= alpha_0 * omega_hat

    Returns True if the price is acceptable.
    """
    min_price = alpha_0 * omega_hat
    return price >= min_price - 1e-10  # Small tolerance for floating point


def compute_seller_payoff(
    price: float, alpha_0: float, omega: float, omega_hat: float
) -> float:
    """Compute the seller's total payoff from an agreement.

    Payoff = P + alpha_0 * (omega - omega_hat)
    The second term represents value from the undisclosed portion.
    """
    return price + alpha_0 * (omega - omega_hat)


def compute_buyer_payoff(omega_hat: float, price: float) -> float:
    """Compute the buyer's payoff from an agreement.

    Payoff = omega_hat - P
    """
    return omega_hat - price


def compute_bilateral_price(alpha_0: float, omega_hat: float, buyer_valuation: float) -> float:
    """Compute bilateral Nash bargaining price.

    P* = (v_b + alpha_0 * omega_hat) / 2

    Derived by maximizing Nash product (P - alpha_0*omega_hat)(v_b - P).
    When v_b = omega_hat, reduces to theta * omega_hat (backward compatible).
    """
    return (buyer_valuation + alpha_0 * omega_hat) / 2


def check_deal_viability(buyer_valuation: float, alpha_0: float, omega_hat: float) -> bool:
    """Check whether a bilateral deal has non-negative surplus.

    Deal is viable when v_b >= alpha_0 * omega_hat (surplus >= 0).
    """
    return buyer_valuation >= alpha_0 * omega_hat - 1e-10


def resolve_bilateral_negotiation(
    params: NegotiationParams, buyer_valuation: float
) -> NegotiationResult:
    """Resolve negotiation using bilateral Nash bargaining.

    Uses buyer's independent valuation v_b to compute:
        P* = (v_b + alpha_0 * omega_hat) / 2

    Steps:
    1. Compute security capacity and disclosure (same as unilateral)
    2. Check deal viability: v_b >= alpha_0 * omega_hat
    3. Compute bilateral price
    4. Check budget cap
    5. Compute payoffs: buyer gets v_b - P*, seller gets P* + alpha_0*(omega - omega_hat)
    """
    phi = security_capacity(params.security_params)
    omega_hat = compute_disclosure(params.omega, phi)
    theta = compute_theta(params.alpha_0)

    # Check deal viability (non-negative surplus)
    if not check_deal_viability(buyer_valuation, params.alpha_0, omega_hat):
        return NegotiationResult(
            outcome=NegotiationOutcomeType.NO_DEAL,
            final_price=None,
            omega_hat=omega_hat,
            theta=theta,
            phi=phi,
            seller_payoff=None,
            buyer_payoff=None,
            buyer_valuation=buyer_valuation,
            reason=(
                f"No surplus: buyer valuation {buyer_valuation:.4f} "
                f"< seller reservation {params.alpha_0 * omega_hat:.4f}"
            ),
        )

    price = compute_bilateral_price(params.alpha_0, omega_hat, buyer_valuation)

    # Check budget cap
    if not check_budget_cap(price, params.budget_cap):
        return NegotiationResult(
            outcome=NegotiationOutcomeType.NO_DEAL,
            final_price=None,
            omega_hat=omega_hat,
            theta=theta,
            phi=phi,
            seller_payoff=None,
            buyer_payoff=None,
            buyer_valuation=buyer_valuation,
            reason=f"Price {price:.6f} exceeds budget cap {params.budget_cap:.6f}",
        )

    seller_payoff = compute_seller_payoff(price, params.alpha_0, params.omega, omega_hat)
    buyer_payoff = buyer_valuation - price

    return NegotiationResult(
        outcome=NegotiationOutcomeType.AGREEMENT,
        final_price=price,
        omega_hat=omega_hat,
        theta=theta,
        phi=phi,
        seller_payoff=seller_payoff,
        buyer_payoff=buyer_payoff,
        buyer_valuation=buyer_valuation,
        reason="Bilateral Nash bargaining equilibrium reached",
    )


def compute_baseline_payoffs(omega: float, alpha_0: float) -> tuple[float, float]:
    """Compute payoffs without the NDAI mechanism (no disclosure).

    Seller gets: alpha_0 * omega (outside option only)
    Buyer gets: 0 (no access to invention)
    """
    return alpha_0 * omega, 0.0


def resolve_negotiation(params: NegotiationParams) -> NegotiationResult:
    """Run the complete NDAI mechanism and determine the outcome.

    This implements the full protocol from Section 4 of the paper:
    1. Compute security capacity Phi
    2. Determine disclosure omega_hat = min(omega, Phi)
    3. Compute theta and equilibrium price P*
    4. Check budget cap and acceptance threshold
    5. Return agreement or no-deal

    This is the deterministic resolution — LLM agents may influence
    omega_hat in the real system, but the final price computation
    and constraint checks are always deterministic.
    """
    phi = security_capacity(params.security_params)
    omega_hat = compute_disclosure(params.omega, phi)
    theta = compute_theta(params.alpha_0)
    price = compute_equilibrium_price(theta, omega_hat)

    # Check buyer's budget cap
    if not check_budget_cap(price, params.budget_cap):
        return NegotiationResult(
            outcome=NegotiationOutcomeType.NO_DEAL,
            final_price=None,
            omega_hat=omega_hat,
            theta=theta,
            phi=phi,
            seller_payoff=None,
            buyer_payoff=None,
            reason=f"Price {price:.6f} exceeds budget cap {params.budget_cap:.6f}",
        )

    # Check seller's acceptance threshold
    if not check_acceptance_threshold(price, params.alpha_0, params.omega, omega_hat):
        min_price = params.alpha_0 * omega_hat
        return NegotiationResult(
            outcome=NegotiationOutcomeType.NO_DEAL,
            final_price=None,
            omega_hat=omega_hat,
            theta=theta,
            phi=phi,
            seller_payoff=None,
            buyer_payoff=None,
            reason=(
                f"Price {price:.6f} below seller threshold "
                f"{min_price:.6f}"
            ),
        )

    seller_payoff = compute_seller_payoff(price, params.alpha_0, params.omega, omega_hat)
    buyer_payoff = compute_buyer_payoff(omega_hat, price)

    return NegotiationResult(
        outcome=NegotiationOutcomeType.AGREEMENT,
        final_price=price,
        omega_hat=omega_hat,
        theta=theta,
        phi=phi,
        seller_payoff=seller_payoff,
        buyer_payoff=buyer_payoff,
        reason="Nash bargaining equilibrium reached",
    )
