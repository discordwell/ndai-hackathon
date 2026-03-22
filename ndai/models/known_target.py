"""Known verification targets — platform-maintained catalog of software to verify 0days against."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class KnownTarget(Base):
    __tablename__ = "known_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # "chrome-linux"
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)  # "Google Chrome (Linux)"
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # "linux" | "windows" | "ios"
    current_version: Mapped[str] = mapped_column(String(100), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(30), nullable=False)  # "nitro" | "ec2_windows" | "corellium" | "manual"

    # Target environment spec (for Nitro/Linux targets)
    base_image: Mapped[str | None] = mapped_column(String(200))  # "ubuntu:22.04"
    packages_json: Mapped[dict | None] = mapped_column(JSON)  # [{"name": "chromium-browser", "version": "..."}]
    services_json: Mapped[dict | None] = mapped_column(JSON)  # [{"name": "...", "start_command": "...", ...}]
    build_steps_json: Mapped[list | None] = mapped_column(JSON)  # ["apt-get install ...", ...]
    config_files_json: Mapped[dict | None] = mapped_column(JSON)  # [{"path": "...", "content": "...", "mode": 644}]
    service_user: Mapped[str] = mapped_column(String(50), default="www-data")

    # PoC submission instructions
    poc_script_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "bash" | "python3" | "html" | "powershell" | "manual"
    poc_instructions: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown instructions for sellers

    # Escrow
    escrow_amount_usd: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    # Display
    icon_emoji: Mapped[str] = mapped_column(String(10), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Auto-update
    version_feed_url: Mapped[str | None] = mapped_column(String(500))
    last_version_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Metadata for Windows/iOS
    platform_config_json: Mapped[dict | None] = mapped_column(JSON)  # AMI ID, Corellium config, etc.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TargetBuild(Base):
    __tablename__ = "target_builds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    build_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "eif" | "docker" | "ami"
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    pcr0: Mapped[str | None] = mapped_column(String(200))
    pcr1: Mapped[str | None] = mapped_column(String(200))
    pcr2: Mapped[str | None] = mapped_column(String(200))
    docker_image_hash: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="building")  # "building" | "ready" | "failed" | "superseded"
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
