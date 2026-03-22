"""Poker game state dataclasses.

All game state lives inside the enclave. The deck, undealt cards, and other
players' hole cards never leave the enclave boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Suit(int, Enum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3


SUIT_SYMBOLS = {Suit.CLUBS: "\u2663", Suit.DIAMONDS: "\u2666", Suit.HEARTS: "\u2665", Suit.SPADES: "\u2660"}
RANK_NAMES = {2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K", 14: "A"}


@dataclass(frozen=True, slots=True)
class Card:
    rank: int  # 2-14 (Ace=14)
    suit: Suit

    def __repr__(self) -> str:
        return f"{RANK_NAMES[self.rank]}{SUIT_SYMBOLS[self.suit]}"

    def to_dict(self) -> dict[str, Any]:
        return {"rank": self.rank, "suit": self.suit.value}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Card:
        return cls(rank=d["rank"], suit=Suit(d["suit"]))


class HandPhase(str, Enum):
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    SETTLING = "settling"


class PlayerAction(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class Pot:
    amount: int  # wei
    eligible_players: list[str] = field(default_factory=list)  # player_ids

    def to_dict(self) -> dict[str, Any]:
        return {"amount": self.amount, "eligible_players": list(self.eligible_players)}


@dataclass
class PlayerSeat:
    seat_index: int
    player_id: str
    wallet_address: str
    stack: int  # wei
    hole_cards: list[Card] = field(default_factory=list)
    is_active: bool = True  # still in current hand
    is_sitting_out: bool = False
    current_bet: int = 0
    has_acted: bool = False
    total_bet_this_hand: int = 0  # total put in across all rounds

    def to_dict(self) -> dict[str, Any]:
        return {
            "seat_index": self.seat_index,
            "player_id": self.player_id,
            "wallet_address": self.wallet_address,
            "stack": self.stack,
            "is_active": self.is_active,
            "is_sitting_out": self.is_sitting_out,
            "current_bet": self.current_bet,
            "has_hole_cards": len(self.hole_cards) > 0,
        }


@dataclass
class HandState:
    hand_number: int
    deck: list[Card] = field(default_factory=list)  # NEVER LEAVES ENCLAVE
    deck_seed: bytes = b""  # NEVER LEAVES ENCLAVE
    deck_seed_hash: str = ""  # sha256(seed) - can be revealed after hand
    community_cards: list[Card] = field(default_factory=list)
    pots: list[Pot] = field(default_factory=list)
    phase: HandPhase = HandPhase.PREFLOP
    dealer_seat: int = 0
    small_blind_seat: int = 0
    big_blind_seat: int = 0
    action_on: int | None = None  # seat index
    min_raise: int = 0
    last_raise_size: int = 0
    current_bet: int = 0  # highest bet this round
    hand_over: bool = False

    def active_players(self, seats: list[PlayerSeat | None]) -> list[PlayerSeat]:
        """Players still in the hand (not folded)."""
        return [s for s in seats if s is not None and s.is_active and not s.is_sitting_out]

    def players_who_can_act(self, seats: list[PlayerSeat | None]) -> list[PlayerSeat]:
        """Active players who aren't all-in."""
        return [s for s in self.active_players(seats) if s.stack > 0]


@dataclass
class TableState:
    table_id: str
    small_blind: int  # wei
    big_blind: int  # wei
    min_buy_in: int  # wei
    max_buy_in: int  # wei
    max_seats: int  # 2-9
    seats: list[PlayerSeat | None] = field(default_factory=list)
    hand: HandState | None = None
    hand_count: int = 0  # total hands played
    dealer_seat: int = 0  # persists across hands for rotation
    action_timeout_sec: int = 30
    escrow_contract: str = ""
    hand_verification: Any = None  # SessionVerificationChain for current hand

    def __post_init__(self) -> None:
        if not self.seats:
            self.seats = [None] * self.max_seats

    def seated_players(self) -> list[PlayerSeat]:
        return [s for s in self.seats if s is not None and not s.is_sitting_out]

    def player_by_id(self, player_id: str) -> PlayerSeat | None:
        for s in self.seats:
            if s is not None and s.player_id == player_id:
                return s
        return None

    def next_occupied_seat(self, from_seat: int) -> int:
        """Find next seat with a non-sitting-out player, wrapping around."""
        for i in range(1, self.max_seats + 1):
            idx = (from_seat + i) % self.max_seats
            seat = self.seats[idx]
            if seat is not None and not seat.is_sitting_out:
                return idx
        return from_seat

    def next_active_seat(self, from_seat: int) -> int | None:
        """Find next seat with an active (not folded, not all-in) player who can act."""
        if self.hand is None:
            return None
        for i in range(1, self.max_seats + 1):
            idx = (from_seat + i) % self.max_seats
            seat = self.seats[idx]
            if seat is not None and seat.is_active and not seat.is_sitting_out and seat.stack > 0:
                return idx
        return None
