"""Poker ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import LargeBinary, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ndai.models.user import Base


class PokerTable(Base):
    __tablename__ = "poker_tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    small_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    big_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    action_timeout_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    escrow_contract: Mapped[str | None] = mapped_column(String(42))
    escrow_deploy_tx: Mapped[str | None] = mapped_column(String(66))
    enclave_id: Mapped[str | None] = mapped_column(String(255))
    attestation_doc: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PokerSeat(Base):
    __tablename__ = "poker_seats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("poker_tables.id"), nullable=False)
    seat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(42), nullable=False)
    buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_stack: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    deposit_tx_hash: Mapped[str | None] = mapped_column(String(66))
    cashout_tx_hash: Mapped[str | None] = mapped_column(String(66))
    cashout_amount: Mapped[int | None] = mapped_column(BigInteger)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("table_id", "seat_index", name="uq_poker_table_seat"),
    )


class PokerHand(Base):
    __tablename__ = "poker_hands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("poker_tables.id"), nullable=False)
    hand_number: Mapped[int] = mapped_column(Integer, nullable=False)
    dealer_seat: Mapped[int] = mapped_column(Integer, nullable=False)
    community_cards: Mapped[dict | None] = mapped_column(JSONB)
    pots_awarded: Mapped[dict | None] = mapped_column(JSONB)
    result_hash: Mapped[str | None] = mapped_column(String(66))
    deck_seed_hash: Mapped[str | None] = mapped_column(String(66))
    verification_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    settlement_tx_hash: Mapped[str | None] = mapped_column(String(66))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("table_id", "hand_number", name="uq_poker_table_hand"),
        Index("ix_poker_hands_table_id_hand_number", "table_id", "hand_number"),
    )


class PokerHandAction(Base):
    __tablename__ = "poker_hand_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("poker_hands.id"), nullable=False)
    seat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_poker_hand_actions_hand_id_sequence", "hand_id", "sequence"),
    )
