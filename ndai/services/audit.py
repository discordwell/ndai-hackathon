"""Audit event logging service."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ndai.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def log_event(
    db: AsyncSession,
    agreement_id: uuid.UUID | None,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Record an audit event."""
    entry = AuditLog(
        agreement_id=agreement_id,
        event_type=event_type,
        actor_id=actor_id,
        metadata_=metadata or {},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    logger.info(
        "Audit: %s agreement=%s actor=%s",
        event_type,
        agreement_id,
        actor_id,
    )
    return entry


async def get_audit_log(
    db: AsyncSession, agreement_id: uuid.UUID
) -> list[AuditLog]:
    """Get audit log entries for an agreement."""
    from sqlalchemy import select

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.agreement_id == agreement_id)
        .order_by(AuditLog.created_at)
    )
    return list(result.scalars().all())
