"""add poker indexes

Revision ID: p6a7b8c9d0e1
Revises: o5f6a7b8c9d0
Create Date: 2026-03-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = "p6a7b8c9d0e1"
down_revision: Union[str, None] = "o5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_poker_hand_actions_hand_id_sequence",
        "poker_hand_actions",
        ["hand_id", "sequence"],
    )
    op.create_index(
        "ix_poker_hands_table_id_hand_number",
        "poker_hands",
        ["table_id", "hand_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_poker_hands_table_id_hand_number", table_name="poker_hands")
    op.drop_index("ix_poker_hand_actions_hand_id_sequence", table_name="poker_hand_actions")
