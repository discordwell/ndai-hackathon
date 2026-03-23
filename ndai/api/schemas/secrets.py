"""Pydantic schemas for Conditional Recall."""

from datetime import datetime

from pydantic import BaseModel, Field


class SecretPolicy(BaseModel):
    allowed_actions: list[str] = Field(..., min_length=1)
    max_uses: int = Field(..., gt=0)


class SecretCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    secret_value: str = Field(..., min_length=1)
    policy: SecretPolicy


class SecretResponse(BaseModel):
    id: str
    name: str
    description: str | None
    policy: dict
    uses_remaining: int
    status: str
    created_at: datetime
    is_owner: bool = False


class SecretUseRequest(BaseModel):
    action: str = Field(..., min_length=1)


class SecretUseResponse(BaseModel):
    action: str
    result: str
    success: bool
    secret_name: str
    attestation_available: bool = True
    policy_report: dict | None = None
    policy_constraints: list[dict] | None = None
    egress_log: list[dict] | None = None
    verification: dict | None = None


class SecretAccessLogResponse(BaseModel):
    id: int
    secret_id: str
    requester_id: str
    requester_display_name: str | None = None
    action_requested: str
    status: str
    result_summary: str | None
    verification_data: dict | None = None
    created_at: datetime
