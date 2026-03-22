"""E2E encrypted messaging models — stores only ciphertext and public key material."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class MessagingPrekey(Base):
    """X3DH prekey bundle — one per identity."""

    __tablename__ = "messaging_prekeys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_pubkey: Mapped[str] = mapped_column(
        String(64), ForeignKey("vuln_identities.public_key"), unique=True, nullable=False
    )
    identity_x25519_pub: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_prekey_pub: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_prekey_sig: Mapped[str] = mapped_column(String(128), nullable=False)
    signed_prekey_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MessagingOTPK(Base):
    """One-time prekey pool for X3DH key agreement."""

    __tablename__ = "messaging_otpks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_pubkey: Mapped[str] = mapped_column(
        String(64), ForeignKey("vuln_identities.public_key"), nullable=False
    )
    otpk_pub: Mapped[str] = mapped_column(String(64), nullable=False)
    otpk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessagingConversation(Base):
    """Conversation channel — DM or deal-linked."""

    __tablename__ = "messaging_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # "dm" or "deal"
    agreement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zk_vuln_agreements.id"), nullable=True
    )
    participant_a: Mapped[str] = mapped_column(
        String(64), ForeignKey("vuln_identities.public_key"), nullable=False
    )
    participant_b: Mapped[str] = mapped_column(
        String(64), ForeignKey("vuln_identities.public_key"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessagingMessage(Base):
    """Encrypted message — server stores only ciphertext and Double Ratchet headers."""

    __tablename__ = "messaging_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_conversations.id"), nullable=False
    )
    sender_pubkey: Mapped[str] = mapped_column(
        String(64), ForeignKey("vuln_identities.public_key"), nullable=False
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)  # base64 AES-256-GCM
    header: Mapped[str] = mapped_column(Text, nullable=False)  # base64 Double Ratchet header
    x3dh_header: Mapped[str | None] = mapped_column(Text, nullable=True)  # base64, first msg only
    message_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
