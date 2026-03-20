"""Pydantic schemas for Props (meeting transcript processing)."""

from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptSubmitRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    team_name: str | None = None
    content: str = Field(..., min_length=10)


class TranscriptResponse(BaseModel):
    id: str
    title: str
    team_name: str | None
    status: str
    content_hash: str
    created_at: datetime


class TranscriptSummaryResponse(BaseModel):
    id: str
    transcript_id: str
    executive_summary: str
    action_items: list[str]
    key_decisions: list[str]
    dependencies: list[str]
    blockers: list[str]
    sentiment: str | None
    attestation_available: bool = True
    created_at: datetime
    policy_report: dict | None = None
    policy_constraints: list[dict] | None = None
    egress_log: list[dict] | None = None
    verification: dict | None = None


class AggregationRequest(BaseModel):
    transcript_ids: list[str] = Field(..., min_length=2)


class AggregationResponse(BaseModel):
    cross_team_summary: str
    shared_dependencies: list[str]
    shared_blockers: list[str]
    recommendations: list[str]
    transcript_count: int
    attestation_available: bool = True
    verification: dict | None = None
