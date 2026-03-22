"""Sealed delivery ORM model — stores encrypted exploit payloads."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class DeliveryRecord(Base):
    __tablename__ = "vuln_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vuln_agreements.id"), unique=True, nullable=False)
    delivery_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)      # AES(K_d, exploit)
    delivery_key_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # ECIES(buyer_pub, K_d)
    delivery_hash: Mapped[str] = mapped_column(String(64), nullable=False)                # SHA-256(delivery_ciphertext)
    key_commitment: Mapped[str] = mapped_column(String(64), nullable=False)               # SHA-256(delivery_key_ciphertext)
    status: Mapped[str] = mapped_column(String(30), default="sealed")                     # sealed, released
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
