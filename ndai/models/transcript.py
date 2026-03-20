"""Meeting transcript and summary ORM models for Props."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submitter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    team_name: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TranscriptSummary(Base):
    __tablename__ = "transcript_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meeting_transcripts.id"), unique=True, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    action_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    key_decisions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    blockers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sentiment: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
