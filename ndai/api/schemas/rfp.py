"""RFP (Request for Proposals) request/response schemas."""

from pydantic import BaseModel, Field


class RFPCreateRequest(BaseModel):
    title: str
    target_software: str
    target_version_range: str
    desired_capability: str  # RCE|LPE|InfoLeak|DoS
    threat_model: str | None = None
    target_environment: dict | None = None
    acceptance_criteria: str | None = None
    budget_min_eth: float = Field(gt=0.0)
    budget_max_eth: float = Field(gt=0.0)
    deadline: str  # ISO 8601
    exclusivity_preference: str = "either"


class RFPUpdateRequest(BaseModel):
    title: str | None = None
    threat_model: str | None = None
    target_environment: dict | None = None
    acceptance_criteria: str | None = None
    budget_min_eth: float | None = None
    budget_max_eth: float | None = None
    deadline: str | None = None
    exclusivity_preference: str | None = None


class RFPResponse(BaseModel):
    id: str
    buyer_id: str
    title: str
    target_software: str
    target_version_range: str
    desired_capability: str
    threat_model: str | None
    target_environment: dict | None
    acceptance_criteria: str | None
    has_patches: bool
    budget_min_eth: float
    budget_max_eth: float
    deadline: str
    exclusivity_preference: str
    status: str
    created_at: str


class RFPListingResponse(BaseModel):
    """Seller-facing RFP listing."""
    id: str
    title: str
    target_software: str
    target_version_range: str
    desired_capability: str
    has_patches: bool
    budget_min_eth: float
    budget_max_eth: float
    deadline: str
    exclusivity_preference: str
    status: str


class RFPProposalCreateRequest(BaseModel):
    vulnerability_id: str | None = None
    message: str | None = None
    proposed_price_eth: float = Field(gt=0.0)
    estimated_delivery_days: int = Field(default=30, gt=0)


class RFPProposalResponse(BaseModel):
    id: str
    rfp_id: str
    seller_id: str
    vulnerability_id: str | None
    message: str | None
    proposed_price_eth: float
    estimated_delivery_days: int
    status: str
    created_at: str
