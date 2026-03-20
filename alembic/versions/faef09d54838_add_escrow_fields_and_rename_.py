"""add escrow fields and rename transaction hash

Revision ID: faef09d54838
Revises: bc3c61b62789
Create Date: 2026-03-19 22:13:39.619727
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'faef09d54838'
down_revision: Union[str, None] = 'bc3c61b62789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('agreements', sa.Column('escrow_address', sa.String(42), nullable=True))
    op.add_column('agreements', sa.Column('escrow_tx_hash', sa.String(66), nullable=True))
    op.alter_column('payments', 'mock_transaction_id', new_column_name='transaction_hash', type_=sa.String(66))


def downgrade() -> None:
    op.alter_column('payments', 'transaction_hash', new_column_name='mock_transaction_id', type_=sa.String(255))
    op.drop_column('agreements', 'escrow_tx_hash')
    op.drop_column('agreements', 'escrow_address')
