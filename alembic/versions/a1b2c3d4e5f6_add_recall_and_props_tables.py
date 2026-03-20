"""add recall and props tables

Revision ID: a1b2c3d4e5f6
Revises: faef09d54838
Create Date: 2026-03-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'faef09d54838'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Secrets table (Conditional Recall)
    op.create_table(
        'secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('encrypted_value', sa.Text(), nullable=False),
        sa.Column('policy', postgresql.JSONB(), nullable=False),
        sa.Column('uses_remaining', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Secret access log
    op.create_table(
        'secret_access_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('secret_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('secrets.id'), nullable=False),
        sa.Column('requester_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action_requested', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Meeting transcripts (Props)
    op.create_table(
        'meeting_transcripts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('submitter_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('team_name', sa.String(255), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='submitted'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Transcript summaries
    op.create_table(
        'transcript_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('transcript_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('meeting_transcripts.id'), unique=True, nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=False),
        sa.Column('action_items', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('key_decisions', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('dependencies', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('blockers', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('sentiment', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('transcript_summaries')
    op.drop_table('meeting_transcripts')
    op.drop_table('secret_access_log')
    op.drop_table('secrets')
