"""Async CRUD repository functions for all models."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.models.agreement import Agreement, AgreementOutcome
from ndai.models.invention import Invention
from ndai.models.user import User
from ndai.models.rfp import BuyerRFP, RFPProposal
from ndai.models.vulnerability import Vulnerability, VulnAgreement, VulnAgreementOutcome


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


async def list_inventions_by_seller(
    db: AsyncSession, seller_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[Invention]:
    result = await db.execute(
        select(Invention).where(Invention.seller_id == seller_id).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def update_invention(db: AsyncSession, invention: Invention, **kwargs) -> Invention:
    for key, value in kwargs.items():
        setattr(invention, key, value)
    await db.commit()
    await db.refresh(invention)
    return invention


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


# ── Vulnerabilities ──

async def create_vulnerability(db: AsyncSession, seller_id: uuid.UUID, **kwargs) -> Vulnerability:
    vuln = Vulnerability(id=uuid.uuid4(), seller_id=seller_id, **kwargs)
    db.add(vuln)
    await db.commit()
    await db.refresh(vuln)
    return vuln


async def get_vulnerability(db: AsyncSession, vuln_id: uuid.UUID) -> Vulnerability | None:
    result = await db.execute(select(Vulnerability).where(Vulnerability.id == vuln_id))
    return result.scalar_one_or_none()


async def list_vulnerabilities_by_seller(db: AsyncSession, seller_id: uuid.UUID) -> list[Vulnerability]:
    result = await db.execute(
        select(Vulnerability).where(Vulnerability.seller_id == seller_id)
    )
    return list(result.scalars().all())


async def list_active_vulnerabilities(db: AsyncSession) -> list[Vulnerability]:
    result = await db.execute(
        select(Vulnerability).where(Vulnerability.status == "active")
    )
    return list(result.scalars().all())


# ── Vuln Agreements ──

async def create_vuln_agreement(db: AsyncSession, **kwargs) -> VulnAgreement:
    agreement = VulnAgreement(id=uuid.uuid4(), **kwargs)
    db.add(agreement)
    await db.commit()
    await db.refresh(agreement)
    return agreement


async def get_vuln_agreement(db: AsyncSession, agreement_id: uuid.UUID) -> VulnAgreement | None:
    result = await db.execute(select(VulnAgreement).where(VulnAgreement.id == agreement_id))
    return result.scalar_one_or_none()


async def list_vuln_agreements_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[VulnAgreement]:
    result = await db.execute(
        select(VulnAgreement).where(
            (VulnAgreement.buyer_id == user_id) | (VulnAgreement.seller_id == user_id)
        )
    )
    return list(result.scalars().all())


_VULN_AGREEMENT_UPDATABLE = frozenset({
    "status", "alpha_0", "budget_cap", "security_params",
    "escrow_address", "escrow_tx_hash", "embargo_expires_at",
    "negotiation_started_at", "completed_at",
})


async def update_vuln_agreement(db: AsyncSession, agreement: VulnAgreement, **kwargs) -> VulnAgreement:
    for key, value in kwargs.items():
        if key not in _VULN_AGREEMENT_UPDATABLE:
            raise ValueError(f"Cannot update vuln agreement field: {key}")
        setattr(agreement, key, value)
    await db.commit()
    await db.refresh(agreement)
    return agreement


# ── Vuln Outcomes ──

async def create_vuln_outcome(db: AsyncSession, **kwargs) -> VulnAgreementOutcome:
    outcome = VulnAgreementOutcome(id=uuid.uuid4(), **kwargs)
    db.add(outcome)
    await db.commit()
    await db.refresh(outcome)
    return outcome


async def get_vuln_outcome_by_agreement(
    db: AsyncSession, agreement_id: uuid.UUID
) -> VulnAgreementOutcome | None:
    result = await db.execute(
        select(VulnAgreementOutcome).where(VulnAgreementOutcome.agreement_id == agreement_id)
    )
    return result.scalar_one_or_none()


# ── Buyer RFPs ──

async def create_rfp(db: AsyncSession, buyer_id: uuid.UUID, **kwargs) -> BuyerRFP:
    rfp = BuyerRFP(id=uuid.uuid4(), buyer_id=buyer_id, **kwargs)
    db.add(rfp)
    await db.commit()
    await db.refresh(rfp)
    return rfp


async def get_rfp(db: AsyncSession, rfp_id: uuid.UUID) -> BuyerRFP | None:
    result = await db.execute(select(BuyerRFP).where(BuyerRFP.id == rfp_id))
    return result.scalar_one_or_none()


async def list_rfps_by_buyer(db: AsyncSession, buyer_id: uuid.UUID) -> list[BuyerRFP]:
    result = await db.execute(select(BuyerRFP).where(BuyerRFP.buyer_id == buyer_id))
    return list(result.scalars().all())


async def list_active_rfps(db: AsyncSession) -> list[BuyerRFP]:
    result = await db.execute(select(BuyerRFP).where(BuyerRFP.status == "active"))
    return list(result.scalars().all())


_RFP_UPDATABLE = frozenset({
    "title", "threat_model", "target_environment", "acceptance_criteria",
    "budget_min_eth", "budget_max_eth", "deadline", "exclusivity_preference",
    "status", "has_patches", "patch_data", "patch_hash",
})


async def update_rfp(db: AsyncSession, rfp: BuyerRFP, **kwargs) -> BuyerRFP:
    for key, value in kwargs.items():
        if key not in _RFP_UPDATABLE:
            raise ValueError(f"Cannot update RFP field: {key}")
        setattr(rfp, key, value)
    await db.commit()
    await db.refresh(rfp)
    return rfp


# ── RFP Proposals ──

async def create_rfp_proposal(db: AsyncSession, **kwargs) -> RFPProposal:
    proposal = RFPProposal(id=uuid.uuid4(), **kwargs)
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def get_rfp_proposal(db: AsyncSession, proposal_id: uuid.UUID) -> RFPProposal | None:
    result = await db.execute(select(RFPProposal).where(RFPProposal.id == proposal_id))
    return result.scalar_one_or_none()


async def list_proposals_for_rfp(db: AsyncSession, rfp_id: uuid.UUID) -> list[RFPProposal]:
    result = await db.execute(select(RFPProposal).where(RFPProposal.rfp_id == rfp_id))
    return list(result.scalars().all())


async def update_rfp_proposal(db: AsyncSession, proposal: RFPProposal, **kwargs) -> RFPProposal:
    for key, value in kwargs.items():
        setattr(proposal, key, value)
    await db.commit()
    await db.refresh(proposal)
    return proposal
