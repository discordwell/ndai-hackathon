"""ZK auction request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ZKAuctionCreateRequest(BaseModel):
    vulnerability_id: str  # UUID
    reserve_price_eth: float = Field(gt=0)
    duration_hours: int = Field(ge=1, le=168)  # 1 hour to 7 days
    serious_customers_only: bool = False


class ZKAuctionBidRequest(BaseModel):
    eth_address: str = Field(min_length=42, max_length=42, pattern=r"^0x[0-9a-fA-F]{40}$")
    bid_tx_hash: str = Field(min_length=66, max_length=66)
    bid_eth: float = Field(gt=0)


class ZKAuctionResponse(BaseModel):
    id: str
    vulnerability_id: str
    seller_pubkey: str
    reserve_price_eth: float
    duration_hours: int
    serious_customers_only: bool
    status: str
    highest_bid_eth: float | None = None
    highest_bidder_pubkey: str | None = None
    end_time: datetime | None = None
    auction_contract_address: str | None = None
    created_at: datetime


class ZKAuctionBidResponse(BaseModel):
    id: str
    auction_id: str
    bidder_pubkey: str
    bid_eth: float
    bid_tx_hash: str | None = None
    is_highest: bool
    created_at: datetime


class SeriousCustomerDepositRequest(BaseModel):
    eth_address: str = Field(min_length=42, max_length=42, pattern=r"^0x[0-9a-fA-F]{40}$")
    tx_hash: str = Field(min_length=66, max_length=66)
    deposit_eth: float = Field(gt=0)


class SeriousCustomerStatusResponse(BaseModel):
    is_serious_customer: bool
    sc_type: str | None = None
    sc_deposit_eth: float | None = None
    sc_eth_address: str | None = None
    sc_awarded_at: datetime | None = None
    sc_refunded: bool = False
    min_deposit_eth: float | None = None


class MinDepositResponse(BaseModel):
    min_deposit_eth: float
    eth_price_usd: float
