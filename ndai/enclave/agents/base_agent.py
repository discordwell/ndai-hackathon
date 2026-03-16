"""Base agent interface and shared data models for NDAI negotiation agents."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class AgentRole(Enum):
    SELLER = "seller_agent"
    BUYER = "buyer_agent"


@dataclass
class InventionSubmission:
    """Structured invention submission from the seller."""

    title: str
    full_description: str
    technical_domain: str
    novelty_claims: list[str]
    prior_art_known: list[str]
    potential_applications: list[str]
    development_stage: str  # concept, prototype, tested, production-ready
    self_assessed_value: float  # omega in [0, 1)
    outside_option_value: float  # alpha_0 in (0, 1]
    confidential_sections: list[str]
    max_disclosure_fraction: float = 1.0


@dataclass
class InventionDisclosure:
    """What the seller agent reveals to the buyer agent."""

    summary: str
    technical_details: str
    disclosed_value: float  # omega_hat
    disclosure_fraction: float  # omega_hat / omega
    withheld_aspects: list[str]


@dataclass
class PriceProposal:
    """A price offer from either agent."""

    proposed_price: float
    reasoning: str
    confidence: float  # 0-1


@dataclass
class AgentMessage:
    """A message from an agent in the negotiation."""

    role: AgentRole
    round_number: int
    disclosure: InventionDisclosure | None = None
    price_proposal: PriceProposal | None = None
    explanation: str = ""
    private_reasoning: str = ""
    raw_response: dict[str, Any] | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
