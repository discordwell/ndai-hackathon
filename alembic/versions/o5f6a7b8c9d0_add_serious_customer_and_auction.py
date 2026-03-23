"""add serious customer fields and auction tables

Revision ID: o5f6a7b8c9d0
Revises: n4e5f6a7b8c9
Create Date: 2026-03-22 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision: str = "o5f6a7b8c9d0"
down_revision: Union[str, None] = "n4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Serious Customer columns on vuln_identities --
    op.add_column("vuln_identities", sa.Column("is_serious_customer", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("vuln_identities", sa.Column("sc_type", sa.String(20), nullable=True))
    op.add_column("vuln_identities", sa.Column("sc_deposit_tx_hash", sa.String(66), nullable=True))
    op.add_column("vuln_identities", sa.Column("sc_deposit_eth", sa.Float(), nullable=True))
    op.add_column("vuln_identities", sa.Column("sc_eth_address", sa.String(42), nullable=True))
    op.add_column("vuln_identities", sa.Column("sc_awarded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("vuln_identities", sa.Column("sc_refunded", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("vuln_identities", sa.Column("sc_refund_tx_hash", sa.String(66), nullable=True))

    # -- serious_customers_only on zk_vulnerabilities --
    op.add_column("zk_vulnerabilities", sa.Column("serious_customers_only", sa.Boolean(), server_default="false", nullable=False))

    # -- Auction table --
    op.create_table(
        "zk_vuln_auctions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("vulnerability_id", UUID(as_uuid=True), sa.ForeignKey("zk_vulnerabilities.id"), nullable=False),
        sa.Column("seller_pubkey", sa.String(64), sa.ForeignKey("vuln_identities.public_key"), nullable=False),
        sa.Column("seller_eth_address", sa.String(42), nullable=True),
        sa.Column("auction_contract_address", sa.String(42), nullable=True),
        sa.Column("auction_tx_hash", sa.String(66), nullable=True),
        sa.Column("reserve_price_eth", sa.Float(), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=False),
        sa.Column("serious_customers_only", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("highest_bid_eth", sa.Float(), nullable=True),
        sa.Column("highest_bidder_pubkey", sa.String(64), nullable=True),
        sa.Column("highest_bidder_eth_address", sa.String(42), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # -- Auction bids table --
    op.create_table(
        "zk_vuln_auction_bids",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("auction_id", UUID(as_uuid=True), sa.ForeignKey("zk_vuln_auctions.id"), nullable=False),
        sa.Column("bidder_pubkey", sa.String(64), sa.ForeignKey("vuln_identities.public_key"), nullable=False),
        sa.Column("bidder_eth_address", sa.String(42), nullable=False),
        sa.Column("bid_eth", sa.Float(), nullable=False),
        sa.Column("bid_tx_hash", sa.String(66), nullable=True),
        sa.Column("is_highest", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("zk_vuln_auction_bids")
    op.drop_table("zk_vuln_auctions")
    op.drop_column("zk_vulnerabilities", "serious_customers_only")
    op.drop_column("vuln_identities", "sc_refund_tx_hash")
    op.drop_column("vuln_identities", "sc_refunded")
    op.drop_column("vuln_identities", "sc_awarded_at")
    op.drop_column("vuln_identities", "sc_eth_address")
    op.drop_column("vuln_identities", "sc_deposit_eth")
    op.drop_column("vuln_identities", "sc_deposit_tx_hash")
    op.drop_column("vuln_identities", "sc_type")
    op.drop_column("vuln_identities", "is_serious_customer")
