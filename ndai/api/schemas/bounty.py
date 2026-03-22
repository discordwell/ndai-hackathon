"""Bounty request/response schemas for buyer-initiated 0day requests."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

IMPACT_TYPES = Literal["RCE", "LPE", "InfoLeak", "DoS"]


class BountyCreateRequest(BaseModel):
    target_software: str = Field(max_length=500)
    target_version_constraint: str | None = Field(default=None, max_length=200)
    desired_impact: IMPACT_TYPES
    desired_vulnerability_class: str | None = Field(default=None, max_length=20)
    budget_eth: float = Field(gt=0.0)
    description: str = Field(max_length=10000)
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
    target_software: str = Field(max_length=500)
    target_version: str = Field(max_length=100)
    vulnerability_class: str = Field(max_length=20)  # CWE-XXX
    impact_type: IMPACT_TYPES
    affected_component: str | None = Field(default=None, max_length=500)
    anonymized_summary: str | None = Field(default=None, max_length=5000)
    cvss_self_assessed: float = Field(ge=0.0, le=10.0)
    asking_price_eth: float = Field(gt=0.0)
    discovery_date: str = Field(max_length=20)  # ISO 8601
