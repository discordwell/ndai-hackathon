"""Async CRUD repository functions for all models."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.models.agreement import Agreement, AgreementOutcome
from ndai.models.invention import Invention
from ndai.models.user import User


# ── Users ──

async def create_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    role: str,
    display_name: str | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=password_hash,
        role=role,
        display_name=display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ── Inventions ──

async def create_invention(db: AsyncSession, seller_id: uuid.UUID, **kwargs) -> Invention:
    invention = Invention(id=uuid.uuid4(), seller_id=seller_id, **kwargs)
    db.add(invention)
    await db.commit()
    await db.refresh(invention)
    return invention


async def get_invention(db: AsyncSession, invention_id: uuid.UUID) -> Invention | None:
    result = await db.execute(select(Invention).where(Invention.id == invention_id))
    return result.scalar_one_or_none()


async def list_inventions_by_seller(db: AsyncSession, seller_id: uuid.UUID) -> list[Invention]:
    result = await db.execute(
        select(Invention).where(Invention.seller_id == seller_id)
    )
    return list(result.scalars().all())


async def list_active_inventions(db: AsyncSession) -> list[Invention]:
    result = await db.execute(
        select(Invention).where(Invention.status == "active")
    )
    return list(result.scalars().all())


# ── Agreements ──

async def create_agreement(db: AsyncSession, **kwargs) -> Agreement:
    agreement = Agreement(id=uuid.uuid4(), **kwargs)
    db.add(agreement)
    await db.commit()
    await db.refresh(agreement)
    return agreement


async def get_agreement(db: AsyncSession, agreement_id: uuid.UUID) -> Agreement | None:
    result = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    return result.scalar_one_or_none()


async def list_agreements_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Agreement]:
    result = await db.execute(
        select(Agreement).where(
            (Agreement.buyer_id == user_id) | (Agreement.seller_id == user_id)
        )
    )
    return list(result.scalars().all())


_AGREEMENT_UPDATABLE = frozenset({
    "status", "alpha_0", "budget_cap", "theta", "security_params",
    "seller_confirmed", "buyer_confirmed", "enclave_id", "attestation_doc",
    "negotiation_started_at", "completed_at",
    "escrow_address", "escrow_tx_hash",
})


async def update_agreement(db: AsyncSession, agreement: Agreement, **kwargs) -> Agreement:
    for key, value in kwargs.items():
        if key not in _AGREEMENT_UPDATABLE:
            raise ValueError(f"Cannot update agreement field: {key}")
        setattr(agreement, key, value)
    await db.commit()
    await db.refresh(agreement)
    return agreement


# ── Outcomes ──

async def create_outcome(db: AsyncSession, **kwargs) -> AgreementOutcome:
    outcome = AgreementOutcome(id=uuid.uuid4(), **kwargs)
    db.add(outcome)
    await db.commit()
    await db.refresh(outcome)
    return outcome


async def get_outcome_by_agreement(
    db: AsyncSession, agreement_id: uuid.UUID
) -> AgreementOutcome | None:
    result = await db.execute(
        select(AgreementOutcome).where(AgreementOutcome.agreement_id == agreement_id)
    )
    return result.scalar_one_or_none()
