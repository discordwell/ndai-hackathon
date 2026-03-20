"""Pydantic schemas for poker API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class CreateTableRequest(BaseModel):
    small_blind: int = Field(..., gt=0)
    big_blind: int = Field(..., gt=0)
    min_buy_in: int = Field(..., gt=0)
    max_buy_in: int = Field(..., gt=0)
    max_seats: int = Field(default=6, ge=2, le=9)
    action_timeout_sec: int = Field(default=30, ge=10, le=120)


class JoinTableRequest(BaseModel):
    buy_in: int = Field(..., gt=0)
    wallet_address: str
    deposit_tx_hash: str = ""
    preferred_seat: int | None = None


class PlayerActionRequest(BaseModel):
    action: str  # fold, check, call, bet, raise, all_in
    amount: int | None = None


class RebuyRequest(BaseModel):
    amount: int = Field(..., gt=0)
    deposit_tx_hash: str = ""


class TableSummaryResponse(BaseModel):
    id: str
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    max_seats: int
    player_count: int
    status: str
    escrow_contract: str | None = None


class TableViewResponse(BaseModel):
    table_view: dict[str, Any]


class GameEventResponse(BaseModel):
    events: list[dict[str, Any]]
    table_view: dict[str, Any] | None = None
    hand_over: bool = False


class HandStartResponse(BaseModel):
    hand_number: int
    events: list[dict[str, Any]]
    # player_hands intentionally excluded — distributed via SSE per-player
