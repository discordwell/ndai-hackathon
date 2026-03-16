"""Invention ORM model."""

import uuid

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
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
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    share_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    shamir_k: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    shamir_n: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(String(30), default="active")
