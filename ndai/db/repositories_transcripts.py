"""Async CRUD repository for Props meeting transcripts."""

import uuid

from sqlalchemy import select
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


async def list_transcripts_by_user(db: AsyncSession, user_id: uuid.UUID) -> list[MeetingTranscript]:
    result = await db.execute(
        select(MeetingTranscript)
        .where(MeetingTranscript.submitter_id == user_id)
        .order_by(MeetingTranscript.created_at.desc())
    )
    return list(result.scalars().all())


async def update_transcript_status(db: AsyncSession, transcript: MeetingTranscript, status: str) -> MeetingTranscript:
    transcript.status = status
    await db.commit()
    await db.refresh(transcript)
    return transcript


async def create_summary(db: AsyncSession, transcript_id: uuid.UUID, **kwargs) -> TranscriptSummary:
    summary = TranscriptSummary(id=uuid.uuid4(), transcript_id=transcript_id, **kwargs)
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
