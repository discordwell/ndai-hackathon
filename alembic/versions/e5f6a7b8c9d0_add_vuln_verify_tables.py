"""add vuln verify tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-22 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vuln_target_specs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("vulnerability_id", UUID(as_uuid=True), sa.ForeignKey("vulnerabilities.id"), nullable=False),
        sa.Column("base_image", sa.String(100), nullable=False),
        sa.Column("packages", JSONB(), nullable=False),
        sa.Column("config_files", JSONB()),
        sa.Column("services", JSONB()),
        sa.Column("poc_hash", sa.String(64)),
        sa.Column("expected_outcome", JSONB()),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "vuln_eif_manifests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("spec_id", UUID(as_uuid=True), sa.ForeignKey("vuln_target_specs.id"), nullable=False),
        sa.Column("eif_path", sa.String(500), nullable=False),
        sa.Column("pcr0", sa.String(200), nullable=False),
        sa.Column("pcr1", sa.String(200), nullable=False),
        sa.Column("pcr2", sa.String(200), nullable=False),
        sa.Column("docker_image_hash", sa.String(100)),
        sa.Column("built_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "vuln_verification_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("spec_id", UUID(as_uuid=True), sa.ForeignKey("vuln_target_specs.id"), nullable=False),
        sa.Column("agreement_id", UUID(as_uuid=True), sa.ForeignKey("vuln_agreements.id"), nullable=False),
        sa.Column("buyer_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("unpatched_exit_code", sa.Integer()),
        sa.Column("unpatched_matches", sa.Boolean(), nullable=False),
        sa.Column("patched_exit_code", sa.Integer()),
        sa.Column("patched_matches", sa.Boolean()),
        sa.Column("overlap_detected", sa.Boolean()),
        sa.Column("verification_chain_hash", sa.String(64), nullable=False),
        sa.Column("attestation_pcr0", sa.String(200)),
        sa.Column("attestation_signature", sa.LargeBinary()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("vuln_verification_results")
    op.drop_table("vuln_eif_manifests")
    op.drop_table("vuln_target_specs")
