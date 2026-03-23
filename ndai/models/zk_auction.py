"""ZK-authenticated auction models for the zero-day marketplace."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ndai.models.user import Base


class ZKVulnAuction(Base):
    __tablename__ = "zk_vuln_auctions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zk_vulnerabilities.id"), nullable=False)
    seller_pubkey: Mapped[str] = mapped_column(String(64), ForeignKey("vuln_identities.public_key"), nullable=False)
    seller_eth_address: Mapped[str | None] = mapped_column(String(42))
    auction_contract_address: Mapped[str | None] = mapped_column(String(42))
    auction_tx_hash: Mapped[str | None] = mapped_column(String(66))
    reserve_price_eth: Mapped[float] = mapped_column(Float, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    serious_customers_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|active|ended|settled|cancelled
    highest_bid_eth: Mapped[float | None] = mapped_column(Float)
    highest_bidder_pubkey: Mapped[str | None] = mapped_column(String(64))
    highest_bidder_eth_address: Mapped[str | None] = mapped_column(String(42))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ZKVulnAuctionBid(Base):
    __tablename__ = "zk_vuln_auction_bids"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zk_vuln_auctions.id"), nullable=False)
    bidder_pubkey: Mapped[str] = mapped_column(String(64), ForeignKey("vuln_identities.public_key"), nullable=False)
    bidder_eth_address: Mapped[str] = mapped_column(String(42), nullable=False)
    bid_eth: Mapped[float] = mapped_column(Float, nullable=False)
    bid_tx_hash: Mapped[str | None] = mapped_column(String(66))
    is_highest: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
