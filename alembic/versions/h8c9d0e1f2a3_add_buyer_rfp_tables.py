"""add buyer rfp and proposal tables

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-03-22 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "h8c9d0e1f2a3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buyer_rfps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("buyer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("target_software", sa.String(500), nullable=False),
        sa.Column("target_version_range", sa.String(200), nullable=False),
        sa.Column("desired_capability", sa.String(20), nullable=False),
        sa.Column("threat_model", sa.Text, nullable=True),
        sa.Column("target_environment", postgresql.JSONB, nullable=True),
        sa.Column("acceptance_criteria", sa.Text, nullable=True),
        sa.Column("has_patches", sa.Boolean, server_default="false"),
        sa.Column("patch_data", sa.LargeBinary, nullable=True),
        sa.Column("patch_hash", sa.String(64), nullable=True),
        sa.Column("budget_min_eth", sa.Float, nullable=False),
        sa.Column("budget_max_eth", sa.Float, nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exclusivity_preference", sa.String(20), server_default="either"),
        sa.Column("status", sa.String(30), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rfp_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rfp_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buyer_rfps.id"), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id"), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("proposed_price_eth", sa.Float, nullable=False),
        sa.Column("estimated_delivery_days", sa.Integer, server_default="30"),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("rfp_proposals")
    op.drop_table("buyer_rfps")
