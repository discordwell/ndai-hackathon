"""Zero-knowledge identity model — stores only Ed25519 public keys."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class VulnIdentity(Base):
    __tablename__ = "vuln_identities"

    public_key: Mapped[str] = mapped_column(String(64), primary_key=True)  # hex Ed25519 pubkey
    alias: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
