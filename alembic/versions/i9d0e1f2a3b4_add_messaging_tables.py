"""add e2e encrypted messaging tables

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-03-22 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # X3DH prekey bundles — one per identity
    op.create_table(
        "messaging_prekeys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_pubkey", sa.String(64), sa.ForeignKey("vuln_identities.public_key"), unique=True, nullable=False),
        sa.Column("identity_x25519_pub", sa.String(64), nullable=False),
        sa.Column("signed_prekey_pub", sa.String(64), nullable=False),
        sa.Column("signed_prekey_sig", sa.String(128), nullable=False),
        sa.Column("signed_prekey_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # One-time prekey pool
    op.create_table(
        "messaging_otpks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_pubkey", sa.String(64), sa.ForeignKey("vuln_identities.public_key"), nullable=False),
        sa.Column("otpk_pub", sa.String(64), nullable=False),
        sa.Column("otpk_index", sa.Integer, nullable=False),
        sa.Column("consumed", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Conversation channels
    op.create_table(
        "messaging_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zk_vuln_agreements.id"), nullable=True),
        sa.Column("participant_a", sa.String(64), sa.ForeignKey("vuln_identities.public_key"), nullable=False),
        sa.Column("participant_b", sa.String(64), sa.ForeignKey("vuln_identities.public_key"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Encrypted messages
    op.create_table(
        "messaging_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messaging_conversations.id"), nullable=False),
        sa.Column("sender_pubkey", sa.String(64), sa.ForeignKey("vuln_identities.public_key"), nullable=False),
        sa.Column("ciphertext", sa.Text, nullable=False),
        sa.Column("header", sa.Text, nullable=False),
        sa.Column("x3dh_header", sa.Text, nullable=True),
        sa.Column("message_index", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes for common queries
    op.create_index("ix_messaging_otpks_owner_unconsumed", "messaging_otpks", ["owner_pubkey", "consumed"])
    op.create_index("ix_messaging_messages_conversation", "messaging_messages", ["conversation_id", "created_at"])
    op.create_index("ix_messaging_messages_expires", "messaging_messages", ["expires_at"])
    op.create_index("ix_messaging_conversations_participants", "messaging_conversations", ["participant_a", "participant_b"])


def downgrade() -> None:
    op.drop_index("ix_messaging_conversations_participants")
    op.drop_index("ix_messaging_messages_expires")
    op.drop_index("ix_messaging_messages_conversation")
    op.drop_index("ix_messaging_otpks_owner_unconsumed")
    op.drop_table("messaging_messages")
    op.drop_table("messaging_conversations")
    op.drop_table("messaging_otpks")
    op.drop_table("messaging_prekeys")
