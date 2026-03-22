"""Zero-knowledge identity model — stores only Ed25519 public keys."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class VulnIdentity(Base):
    __tablename__ = "vuln_identities"

    public_key: Mapped[str] = mapped_column(String(64), primary_key=True)  # hex Ed25519 pubkey
    alias: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ⚡ Badge — no tire kicker verification
    has_badge: Mapped[bool] = mapped_column(Boolean, default=False, insert_default=False, server_default="false")
    badge_type: Mapped[str | None] = mapped_column(String(20))  # "purchased" | "earned"
    badge_tx_hash: Mapped[str | None] = mapped_column(String(66))
    badge_awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
