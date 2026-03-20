"""Async CRUD repository for Conditional Recall secrets."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.models.secret import Secret, SecretAccessLog


async def create_secret(
    db: AsyncSession,
    owner_id: uuid.UUID,
    name: str,
    encrypted_value: str,
    policy: dict,
    description: str | None = None,
) -> Secret:
    secret = Secret(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name=name,
        description=description,
        encrypted_value=encrypted_value,
        policy=policy,
        uses_remaining=policy["max_uses"],
    )
    db.add(secret)
    await db.commit()
    await db.refresh(secret)
    return secret


async def get_secret(db: AsyncSession, secret_id: uuid.UUID) -> Secret | None:
    result = await db.execute(select(Secret).where(Secret.id == secret_id))
    return result.scalar_one_or_none()


async def list_secrets_by_owner(db: AsyncSession, owner_id: uuid.UUID) -> list[Secret]:
    result = await db.execute(
        select(Secret).where(Secret.owner_id == owner_id).order_by(Secret.created_at.desc())
    )
    return list(result.scalars().all())


async def list_available_secrets(db: AsyncSession) -> list[Secret]:
    result = await db.execute(
        select(Secret)
        .where(Secret.status == "active", Secret.uses_remaining > 0)
        .order_by(Secret.created_at.desc())
    )
    return list(result.scalars().all())


async def try_claim_use(db: AsyncSession, secret_id: uuid.UUID) -> bool:
    """Atomically decrement uses_remaining. Returns True if a use was claimed."""
    result = await db.execute(
        update(Secret)
        .where(Secret.id == secret_id, Secret.uses_remaining > 0, Secret.status == "active")
        .values(uses_remaining=Secret.uses_remaining - 1)
    )
    if result.rowcount == 1:
        # Check if now depleted
        secret = await get_secret(db, secret_id)
        if secret and secret.uses_remaining <= 0:
            secret.status = "depleted"
        await db.commit()
        return True
    await db.rollback()
    return False


async def create_access_log(
    db: AsyncSession,
    secret_id: uuid.UUID,
    requester_id: uuid.UUID,
    action_requested: str,
    status: str,
    result_summary: str | None = None,
    verification_data: dict | None = None,
) -> SecretAccessLog:
    log = SecretAccessLog(
        secret_id=secret_id,
        requester_id=requester_id,
        action_requested=action_requested,
        status=status,
        result_summary=result_summary,
        verification_data=verification_data,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_access_logs(db: AsyncSession, secret_id: uuid.UUID) -> list[SecretAccessLog]:
    result = await db.execute(
        select(SecretAccessLog)
        .where(SecretAccessLog.secret_id == secret_id)
        .order_by(SecretAccessLog.created_at.desc())
    )
    return list(result.scalars().all())
