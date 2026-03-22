"""Buyer RFP (Request for Proposals) and proposal ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class BuyerRFP(Base):
    """A buyer's request for a specific vulnerability."""

    __tablename__ = "buyer_rfps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    target_software: Mapped[str] = mapped_column(String(500), nullable=False)
    target_version_range: Mapped[str] = mapped_column(String(200), nullable=False)
    desired_capability: Mapped[str] = mapped_column(String(20), nullable=False)  # RCE|LPE|InfoLeak|DoS
    threat_model: Mapped[str | None] = mapped_column(Text)
    target_environment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    has_patches: Mapped[bool] = mapped_column(Boolean, default=False)
    patch_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    patch_hash: Mapped[str | None] = mapped_column(String(64))
    budget_min_eth: Mapped[float] = mapped_column(Float, nullable=False)
    budget_max_eth: Mapped[float] = mapped_column(Float, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exclusivity_preference: Mapped[str] = mapped_column(String(20), default="either")
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RFPProposal(Base):
    """A seller's proposal in response to a buyer RFP."""

    __tablename__ = "rfp_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rfp_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("buyer_rfps.id"), nullable=False)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vulnerability_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vulnerabilities.id"), nullable=True)
    message: Mapped[str | None] = mapped_column(Text)
    proposed_price_eth: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_delivery_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
