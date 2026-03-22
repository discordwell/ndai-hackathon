"""Pydantic schemas for known targets and verification proposals."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PLATFORM_TYPES = Literal["linux", "windows", "ios"]
VERIFICATION_METHODS = Literal["nitro", "ec2_windows", "corellium", "manual"]
POC_SCRIPT_TYPES = Literal["bash", "python3", "html", "powershell", "manual"]
CAPABILITY_LEVELS = Literal["ace", "lpe", "info_leak", "callback", "crash", "dos"]
PROPOSAL_STATUSES = Literal[
    "pending_deposit", "queued", "building", "verifying",
    "passed", "failed", "refunded", "forfeited", "manual_review",
]


# ── Known Targets ──


class KnownTargetResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    platform: str
    current_version: str
    verification_method: str
    poc_script_type: str
    poc_instructions: str
    escrow_amount_usd: int
    icon_emoji: str
    is_active: bool
    has_prebuilt: bool = False  # computed: whether a ready TargetBuild exists
    created_at: datetime
    updated_at: datetime


class KnownTargetDetailResponse(KnownTargetResponse):
    """Extended detail including build info and platform config."""
    base_image: str | None = None
    service_user: str = "www-data"
    platform_config_json: dict | None = None
    build_status: str | None = None  # latest build status
    build_version: str | None = None  # latest build version


class TargetBuildResponse(BaseModel):
    id: str
    version: str
    build_type: str
    cache_key: str
    status: str
    pcr0: str | None = None
    built_at: datetime


# ── Verification Proposals ──


class ProposalCreateRequest(BaseModel):
    target_id: str  # UUID
    poc_script: str = Field(max_length=262144)  # 256KB
    poc_script_type: POC_SCRIPT_TYPES
    claimed_capability: CAPABILITY_LEVELS
    reliability_runs: int = Field(default=3, ge=1, le=20)
    asking_price_eth: float = Field(gt=0.0)


class ProposalResponse(BaseModel):
    id: str
    seller_pubkey: str
    target_id: str
    target_name: str = ""
    target_version: str
    poc_script_type: str
    claimed_capability: str
    reliability_runs: int
    asking_price_eth: float
    deposit_required: bool
    deposit_amount_wei: str | None = None
    deposit_proposal_id: str | None = None  # bytes32 hex for on-chain contract
    status: str
    created_vuln_id: str | None = None
    error_details: str | None = None
    created_at: datetime
    updated_at: datetime


class ProposalDetailResponse(ProposalResponse):
    """Extended detail with verification results."""
    verification_result_json: dict | None = None
    verification_chain_hash: str | None = None
    attestation_pcr0: str | None = None


class DepositConfirmRequest(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66, pattern=r"^0x[0-9a-fA-F]{64}$")


class ProposalStatusResponse(BaseModel):
    status: str
    verification_result: dict | None = None
    error_details: str | None = None


# ── Badges ──


class BadgeStatusResponse(BaseModel):
    has_badge: bool
    badge_type: str | None = None  # "purchased" | "earned"
    badge_tx_hash: str | None = None
    badge_awarded_at: datetime | None = None


class BadgePurchaseRequest(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66, pattern=r"^0x[0-9a-fA-F]{64}$")
    eth_address: str = Field(min_length=42, max_length=42, pattern=r"^0x[0-9a-fA-F]{40}$")
