"""Transparency report schema."""

from pydantic import BaseModel


class TransparencyReport(BaseModel):
    agreement_id: str
    outcome: str
    final_price: float | None
    transcript_hash: str | None = None
    transcript_signature: str | None = None
    enclave_public_key: str | None = None
    negotiation_rounds: int | None = None
    timestamp: str | None = None
    verification_steps: list[str] = []


class AuditLogEntry(BaseModel):
    id: int
    agreement_id: str | None
    event_type: str
    actor_id: str | None
    metadata: dict | None
    created_at: str
