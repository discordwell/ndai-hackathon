"""Bounty request model for buyer-initiated 0day requests."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class Bounty(Base):
    __tablename__ = "bounties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_pubkey: Mapped[str] = mapped_column(String(64), ForeignKey("vuln_identities.public_key"), nullable=False)
    target_software: Mapped[str] = mapped_column(String(500), nullable=False)
    target_version_constraint: Mapped[str | None] = mapped_column(String(200))
    desired_impact: Mapped[str] = mapped_column(String(20), nullable=False)
    desired_vulnerability_class: Mapped[str | None] = mapped_column(String(20))
    budget_eth: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
