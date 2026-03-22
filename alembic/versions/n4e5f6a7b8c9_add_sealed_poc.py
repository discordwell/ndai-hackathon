"""add sealed_poc columns for encrypted PoC submission

Revision ID: n4e5f6a7b8c9
Revises: m3b4c5d6e7f8
Create Date: 2026-03-22 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "n4e5f6a7b8c9"
down_revision: Union[str, None] = "m3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sealed_poc columns for ECIES-encrypted PoC submissions
    op.add_column("verification_proposals", sa.Column("sealed_poc", sa.LargeBinary(), nullable=True))
    op.add_column("verification_proposals", sa.Column("sealed_poc_hash", sa.String(64), nullable=True))

    # Make poc_script nullable (was NOT NULL — new submissions may use sealed_poc instead)
    op.alter_column("verification_proposals", "poc_script", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("verification_proposals", "poc_script", existing_type=sa.Text(), nullable=False)
    op.drop_column("verification_proposals", "sealed_poc_hash")
    op.drop_column("verification_proposals", "sealed_poc")
