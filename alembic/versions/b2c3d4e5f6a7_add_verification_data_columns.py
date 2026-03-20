"""add verification_data JSONB columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-20 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('secret_access_log', sa.Column('verification_data', postgresql.JSONB(), nullable=True))
    op.add_column('transcript_summaries', sa.Column('verification_data', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('transcript_summaries', 'verification_data')
    op.drop_column('secret_access_log', 'verification_data')
