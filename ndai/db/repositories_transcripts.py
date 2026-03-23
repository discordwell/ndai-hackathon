"""Async CRUD repository for Props meeting transcripts."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.models.transcript import MeetingTranscript, TranscriptSummary


async def create_transcript(
    db: AsyncSession,
    submitter_id: uuid.UUID,
    title: str,
    content_hash: str,
    team_name: str | None = None,
) -> MeetingTranscript:
    transcript = MeetingTranscript(
        id=uuid.uuid4(),
        submitter_id=submitter_id,
        title=title,
        content_hash=content_hash,
        team_name=team_name,
    )
    db.add(transcript)
    await db.commit()
    await db.refresh(transcript)
    return transcript


async def get_transcript(db: AsyncSession, transcript_id: uuid.UUID) -> MeetingTranscript | None:
    result = await db.execute(select(MeetingTranscript).where(MeetingTranscript.id == transcript_id))
    return result.scalar_one_or_none()


async def list_transcripts_by_user(
    db: AsyncSession, user_id: uuid.UUID, offset: int = 0, limit: int = 25,
) -> list[MeetingTranscript]:
    result = await db.execute(
        select(MeetingTranscript)
        .where(MeetingTranscript.submitter_id == user_id)
        .order_by(MeetingTranscript.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_transcripts_by_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(MeetingTranscript.id))
        .where(MeetingTranscript.submitter_id == user_id)
    )
    return result.scalar_one()


async def get_transcripts_by_ids(db: AsyncSession, transcript_ids: list[uuid.UUID]) -> list[MeetingTranscript]:
    result = await db.execute(
        select(MeetingTranscript).where(MeetingTranscript.id.in_(transcript_ids))
    )
    return list(result.scalars().all())


async def update_transcript_status(db: AsyncSession, transcript: MeetingTranscript, status: str) -> MeetingTranscript:
    transcript.status = status
    await db.commit()
    await db.refresh(transcript)
    return transcript


async def create_summary(
    db: AsyncSession,
    transcript_id: uuid.UUID,
    executive_summary: str,
    action_items: list | None = None,
    key_decisions: list | None = None,
    dependencies: list | None = None,
    blockers: list | None = None,
    sentiment: str | None = None,
    verification_data: dict | None = None,
) -> TranscriptSummary:
    summary = TranscriptSummary(
        id=uuid.uuid4(),
        transcript_id=transcript_id,
        executive_summary=executive_summary,
        action_items=action_items or [],
        key_decisions=key_decisions or [],
        dependencies=dependencies or [],
        blockers=blockers or [],
        sentiment=sentiment,
        verification_data=verification_data,
    )
    db.add(summary)
    await db.commit()
    await db.refresh(summary)
    return summary


async def get_summary_by_transcript(db: AsyncSession, transcript_id: uuid.UUID) -> TranscriptSummary | None:
    result = await db.execute(
        select(TranscriptSummary).where(TranscriptSummary.transcript_id == transcript_id)
    )
    return result.scalar_one_or_none()


async def list_summaries_by_ids(db: AsyncSession, transcript_ids: list[uuid.UUID]) -> list[TranscriptSummary]:
    result = await db.execute(
        select(TranscriptSummary).where(TranscriptSummary.transcript_id.in_(transcript_ids))
    )
    return list(result.scalars().all())
