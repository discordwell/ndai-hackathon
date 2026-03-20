"""Agreement and outcome ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class Agreement(Base):
    __tablename__ = "agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invention_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inventions.id"), nullable=False)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    alpha_0: Mapped[float | None] = mapped_column(Float)
    budget_cap: Mapped[float | None] = mapped_column(Float)
    theta: Mapped[float | None] = mapped_column(Float)
    security_params: Mapped[dict | None] = mapped_column(JSONB)
    seller_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    buyer_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    enclave_id: Mapped[str | None] = mapped_column(String(255))
    attestation_doc: Mapped[bytes | None] = mapped_column(LargeBinary)
    escrow_address: Mapped[str | None] = mapped_column(String(42))
    escrow_tx_hash: Mapped[str | None] = mapped_column(String(66))
    negotiation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgreementOutcome(Base):
    __tablename__ = "agreement_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agreements.id"), unique=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # agreement, no_deal, error
    final_price: Mapped[float | None] = mapped_column(Float)
    omega_hat: Mapped[float | None] = mapped_column(Float)
    negotiation_rounds: Mapped[int | None] = mapped_column(Integer)
    encrypted_transcript: Mapped[bytes | None] = mapped_column(LargeBinary)
    transcript_key_ref: Mapped[str | None] = mapped_column(String(255))
    error_details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
