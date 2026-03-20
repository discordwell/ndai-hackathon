"""add poker tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "poker_tables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("small_blind", sa.BigInteger(), nullable=False),
        sa.Column("big_blind", sa.BigInteger(), nullable=False),
        sa.Column("min_buy_in", sa.BigInteger(), nullable=False),
        sa.Column("max_buy_in", sa.BigInteger(), nullable=False),
        sa.Column("max_seats", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("action_timeout_sec", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("escrow_contract", sa.String(42)),
        sa.Column("escrow_deploy_tx", sa.String(66)),
        sa.Column("enclave_id", sa.String(255)),
        sa.Column("attestation_doc", sa.LargeBinary()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "poker_seats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", UUID(as_uuid=True), sa.ForeignKey("poker_tables.id"), nullable=False),
        sa.Column("seat_index", sa.Integer(), nullable=False),
        sa.Column("player_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("wallet_address", sa.String(42), nullable=False),
        sa.Column("buy_in", sa.BigInteger(), nullable=False),
        sa.Column("current_stack", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deposit_tx_hash", sa.String(66)),
        sa.Column("cashout_tx_hash", sa.String(66)),
        sa.Column("cashout_amount", sa.BigInteger()),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("table_id", "seat_index", name="uq_poker_table_seat"),
    )

    op.create_table(
        "poker_hands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", UUID(as_uuid=True), sa.ForeignKey("poker_tables.id"), nullable=False),
        sa.Column("hand_number", sa.Integer(), nullable=False),
        sa.Column("dealer_seat", sa.Integer(), nullable=False),
        sa.Column("community_cards", JSONB()),
        sa.Column("pots_awarded", JSONB()),
        sa.Column("result_hash", sa.String(66)),
        sa.Column("deck_seed_hash", sa.String(66)),
        sa.Column("settlement_tx_hash", sa.String(66)),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("table_id", "hand_number", name="uq_poker_table_hand"),
    )

    op.create_table(
        "poker_hand_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("hand_id", UUID(as_uuid=True), sa.ForeignKey("poker_hands.id"), nullable=False),
        sa.Column("seat_index", sa.Integer(), nullable=False),
        sa.Column("player_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("poker_hand_actions")
    op.drop_table("poker_hands")
    op.drop_table("poker_seats")
    op.drop_table("poker_tables")
