"""Invention ORM model."""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ndai.models.user import Base


class Invention(Base):
    __tablename__ = "inventions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    anonymized_summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    encrypted_payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    share_refs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    shamir_k: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    shamir_n: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(String(30), default="active")

    # Negotiation fields (stored for API, fed into InventionSubmission)
    full_description: Mapped[str | None] = mapped_column(Text)
    technical_domain: Mapped[str | None] = mapped_column(String(100))
    novelty_claims: Mapped[list | None] = mapped_column(JSONB)
    prior_art_known: Mapped[list | None] = mapped_column(JSONB)
    potential_applications: Mapped[list | None] = mapped_column(JSONB)
    development_stage: Mapped[str | None] = mapped_column(String(30))
    self_assessed_value: Mapped[float | None] = mapped_column(Float)
    outside_option_value: Mapped[float | None] = mapped_column(Float)
    confidential_sections: Mapped[list | None] = mapped_column(JSONB)
    max_disclosure_fraction: Mapped[float | None] = mapped_column(Float, default=1.0)
