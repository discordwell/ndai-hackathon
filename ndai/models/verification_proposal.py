"""Verification proposals — seller submits a PoC against a known target."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class VerificationProposal(Base):
    __tablename__ = "verification_proposals"
    __table_args__ = (
        Index("ix_verification_proposals_seller_pubkey", "seller_pubkey"),
        Index("ix_verification_proposals_target_id", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_pubkey: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("known_targets.id"), nullable=False
    )
    target_version: Mapped[str] = mapped_column(String(100), nullable=False)  # snapshot at time of proposal

    # PoC details
    poc_script: Mapped[str] = mapped_column(Text, nullable=False)
    poc_script_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "bash" | "python3" | "html" | "powershell"
    claimed_capability: Mapped[str] = mapped_column(String(20), nullable=False)  # "ace" | "lpe" | "info_leak" | "callback" | "crash" | "dos"
    reliability_runs: Mapped[int] = mapped_column(Integer, default=3)
    asking_price_eth: Mapped[float] = mapped_column(Float, nullable=False)

    # Escrow tracking
    deposit_required: Mapped[bool] = mapped_column(Boolean, default=True)
    deposit_amount_wei: Mapped[str | None] = mapped_column(String(78))  # string to handle large uint256
    deposit_tx_hash: Mapped[str | None] = mapped_column(String(66))
    deposit_proposal_id: Mapped[str | None] = mapped_column(String(66))  # bytes32 hex for on-chain

    # Status lifecycle
    status: Mapped[str] = mapped_column(String(30), default="pending_deposit", server_default="pending_deposit")
    # pending_deposit | queued | building | verifying | passed | failed | refunded | forfeited | manual_review

    # Verification results
    verification_result_json: Mapped[dict | None] = mapped_column(JSON)
    verification_chain_hash: Mapped[str | None] = mapped_column(String(64))
    attestation_pcr0: Mapped[str | None] = mapped_column(String(200))

    # On success, links to the auto-created marketplace listing
    created_vuln_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    error_details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
