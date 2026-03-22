"""Bounty request/response schemas for buyer-initiated 0day requests."""

from datetime import datetime

from pydantic import BaseModel, Field


class BountyCreateRequest(BaseModel):
    target_software: str
    target_version_constraint: str | None = None
    desired_impact: str  # RCE|LPE|InfoLeak|DoS
    desired_vulnerability_class: str | None = None
    budget_eth: float = Field(gt=0.0)
    description: str
    deadline: datetime | None = None  # ISO datetime


class BountyResponse(BaseModel):
    id: str
    requester_pubkey: str
    target_software: str
    target_version_constraint: str | None
    desired_impact: str
    desired_vulnerability_class: str | None
    budget_eth: float
    description: str
    deadline: datetime | None
    status: str
    created_at: datetime


class BountyListingResponse(BaseModel):
    """All fields visible -- buyers WANT to be found."""

    id: str
    requester_pubkey: str
    target_software: str
    target_version_constraint: str | None
    desired_impact: str
    desired_vulnerability_class: str | None
    budget_eth: float
    description: str
    deadline: datetime | None
    status: str
    created_at: datetime


class BountyRespondRequest(BaseModel):
    target_software: str
    target_version: str
    vulnerability_class: str  # CWE-XXX
    impact_type: str  # RCE|LPE|InfoLeak|DoS
    affected_component: str | None = None
    anonymized_summary: str | None = None
    cvss_self_assessed: float = Field(ge=0.0, le=10.0)
    asking_price_eth: float = Field(gt=0.0)
    discovery_date: str  # ISO 8601
