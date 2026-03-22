"""Verification ORM models — target specs, EIF manifests, verification results."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class TargetSpecRecord(Base):
    __tablename__ = "vuln_target_specs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vulnerabilities.id"), nullable=False)
    base_image: Mapped[str] = mapped_column(String(100), nullable=False)
    packages: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config_files: Mapped[dict | None] = mapped_column(JSONB)
    services: Mapped[dict | None] = mapped_column(JSONB)
    poc_hash: Mapped[str | None] = mapped_column(String(64))
    expected_outcome: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EIFManifestRecord(Base):
    __tablename__ = "vuln_eif_manifests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spec_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vuln_target_specs.id"), nullable=False)
    eif_path: Mapped[str] = mapped_column(String(500), nullable=False)
    pcr0: Mapped[str] = mapped_column(String(200), nullable=False)
    pcr1: Mapped[str] = mapped_column(String(200), nullable=False)
    pcr2: Mapped[str] = mapped_column(String(200), nullable=False)
    docker_image_hash: Mapped[str | None] = mapped_column(String(100))
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VerificationResultRecord(Base):
    __tablename__ = "vuln_verification_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spec_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vuln_target_specs.id"), nullable=False)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vuln_agreements.id"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    claimed_capability: Mapped[str | None] = mapped_column(String(20))  # ace, lpe, etc.
    verified_level: Mapped[str | None] = mapped_column(String(20))
    reliability_score: Mapped[float | None] = mapped_column(Float)
    unpatched_result: Mapped[dict | None] = mapped_column(JSONB)  # CapabilityResult as dict
    patched_result: Mapped[dict | None] = mapped_column(JSONB)
    overlap_detected: Mapped[bool | None] = mapped_column(Boolean)
    verification_chain_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attestation_pcr0: Mapped[str | None] = mapped_column(String(200))
    attestation_signature: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
