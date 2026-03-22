"""Base agent interface and shared data models for NDAI negotiation agents."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class AgentRole(Enum):
    SELLER = "seller_agent"
    BUYER = "buyer_agent"
    VULN_SELLER = "vuln_seller_agent"
    VULN_BUYER = "vuln_buyer_agent"


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


@dataclass
class VulnerabilitySubmission:
    """Structured vulnerability submission from the seller."""

    target_software: str  # e.g., "Apache httpd"
    target_version: str  # e.g., "2.4.x"
    vulnerability_class: str  # CWE ID, e.g., "CWE-787"
    impact_type: str  # "RCE" | "LPE" | "InfoLeak" | "DoS"
    affected_component: str  # e.g., "mod_proxy"
    cvss_self_assessed: float  # Seller's CVSS score [0.0, 10.0]
    discovery_date: str  # ISO 8601
    patch_status: str  # "unpatched" | "patch_pending" | "patched"
    exclusivity: str  # "exclusive" | "non-exclusive"
    outside_option_value: float  # alpha_0 in (0, 1]
    poc_code_encrypted: bytes | None = None  # Encrypted PoC, only decrypted in enclave
    max_disclosure_level: int = 3  # Maximum level seller allows (0-3)
    embargo_days: int = 90  # Default embargo period
    poc_hash: str = ""  # SHA-256 hash of plaintext PoC (for verification)
    software_category: str = "default"  # For decay rate lookup


@dataclass
class VulnDisclosure:
    """What the vulnerability seller agent reveals at each level.

    Level 0: vulnerability_class + impact_type only
    Level 1: + affected_component + attack_surface
    Level 2: + trigger_conditions + constraints
    Level 3: + poc_summary (text description, NOT actual code)
    """

    level: int  # 0-3
    level_fraction: float  # level / 3.0 (normalized omega_hat)
    vulnerability_class: str  # Always revealed (level 0+)
    impact_type: str  # Always revealed (level 0+)
    affected_component: str | None = None  # Level 1+
    attack_surface: str | None = None  # Level 1+
    trigger_conditions: str | None = None  # Level 2+
    constraints: str | None = None  # Level 2+
    poc_summary: str | None = None  # Level 3 only (text summary, not code)
    withheld_aspects: list[str] = field(default_factory=list)
