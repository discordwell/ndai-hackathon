"""Per-player view filtering.

Strips sensitive information (other players' hole cards, deck state)
before data leaves the enclave.
"""

from __future__ import annotations

from typing import Any

from ndai.enclave.poker.state import TableState


def make_table_view(table: TableState, player_id: str | None = None) -> dict[str, Any]:
    """Create a filtered table view for a specific player.

    - Other players' hole cards are hidden (replaced with has_hole_cards flag)
    - Deck and seed are never included
    - At showdown, revealed cards are included for players who showed
    """
    hand = table.hand

    seats: list[dict[str, Any] | None] = []
    for seat in table.seats:
        if seat is None:
            seats.append(None)
            continue

        seat_view: dict[str, Any] = {
            "seat_index": seat.seat_index,
            "player_id": seat.player_id,
            "wallet_address": seat.wallet_address,
            "stack": seat.stack,
            "is_active": seat.is_active,
            "is_sitting_out": seat.is_sitting_out,
            "current_bet": seat.current_bet,
            "has_hole_cards": len(seat.hole_cards) > 0,
        }

        # Only include hole cards for the requesting player
        if player_id and seat.player_id == player_id:
            seat_view["hole_cards"] = [c.to_dict() for c in seat.hole_cards]
        else:
            seat_view["hole_cards"] = None

        seats.append(seat_view)

    view: dict[str, Any] = {
        "table_id": table.table_id,
        "small_blind": table.small_blind,
        "big_blind": table.big_blind,
        "min_buy_in": table.min_buy_in,
        "max_buy_in": table.max_buy_in,
        "max_seats": table.max_seats,
        "seats": seats,
        "escrow_contract": table.escrow_contract,
    }

    if hand is not None:
        view["hand_number"] = hand.hand_number
        view["phase"] = hand.phase.value
        view["dealer_seat"] = hand.dealer_seat
        view["small_blind_seat"] = hand.small_blind_seat
        view["big_blind_seat"] = hand.big_blind_seat
        view["action_on"] = hand.action_on
        view["community_cards"] = [c.to_dict() for c in hand.community_cards]
        view["pots"] = [p.to_dict() for p in hand.pots]
        view["current_bet"] = hand.current_bet
        view["min_raise"] = hand.min_raise
    else:
        view["hand_number"] = None
        view["phase"] = "waiting"
        view["dealer_seat"] = None
        view["action_on"] = None
        view["community_cards"] = []
        view["pots"] = []

    return view
