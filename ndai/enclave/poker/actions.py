"""Enclave-side action handlers for poker.

Each handler receives the request dict and a reference to the poker_tables
state dict. Returns a response dict to send back to the parent.
"""

from __future__ import annotations

import logging
from typing import Any

from ndai.enclave.poker.engine import (
    PokerEngineError,
    get_valid_actions,
    process_action,
    process_timeout,
    start_hand,
)
from ndai.enclave.poker.state import PlayerAction, PlayerSeat, TableState
from ndai.enclave.poker.views import make_table_view
from ndai.enclave.verification import SessionVerificationChain

logger = logging.getLogger(__name__)


def handle_poker_action(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    """Top-level dispatcher for all poker_* actions."""
    action = request.get("action", "")

    handlers = {
        "poker_create_table": _handle_create_table,
        "poker_join_table": _handle_join_table,
        "poker_leave_table": _handle_leave_table,
        "poker_start_hand": _handle_start_hand,
        "poker_action": _handle_player_action,
        "poker_timeout": _handle_timeout,
        "poker_get_table": _handle_get_table,
        "poker_rebuy": _handle_rebuy,
    }

    handler = handlers.get(action)
    if handler is None:
        return {"status": "error", "error": f"Unknown poker action: {action}"}

    try:
        return handler(request, poker_tables)
    except PokerEngineError as exc:
        logger.warning("Poker engine error: %s", exc)
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected poker error")
        return {"status": "error", "error": "Internal poker error"}


def _handle_create_table(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table_id = request.get("table_id")
    if not table_id:
        return {"status": "error", "error": "Missing table_id"}
    if table_id in poker_tables:
        return {"status": "error", "error": f"Table {table_id} already exists"}

    max_seats = int(request.get("max_seats", 6))
    if max_seats < 2 or max_seats > 9:
        return {"status": "error", "error": "max_seats must be 2-9"}

    table = TableState(
        table_id=table_id,
        small_blind=int(request["small_blind"]),
        big_blind=int(request["big_blind"]),
        min_buy_in=int(request["min_buy_in"]),
        max_buy_in=int(request["max_buy_in"]),
        max_seats=max_seats,
        action_timeout_sec=int(request.get("action_timeout_sec", 30)),
        escrow_contract=request.get("escrow_contract", ""),
    )

    poker_tables[table_id] = table
    logger.info("Poker table created: %s (%d seats, %d/%d blinds)",
                table_id, max_seats, table.small_blind, table.big_blind)

    return {"status": "ok", "table_id": table_id}


def _handle_join_table(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table = _get_table(request, poker_tables)
    if isinstance(table, dict):
        return table  # error response

    player_id = request.get("player_id")
    wallet_address = request.get("wallet_address", "")
    buy_in = int(request.get("buy_in", 0))

    if not player_id:
        return {"status": "error", "error": "Missing player_id"}
    if buy_in < table.min_buy_in:
        return {"status": "error", "error": f"Buy-in {buy_in} below minimum {table.min_buy_in}"}
    if buy_in > table.max_buy_in:
        return {"status": "error", "error": f"Buy-in {buy_in} above maximum {table.max_buy_in}"}

    # Check if player is already seated
    existing = table.player_by_id(player_id)
    if existing is not None:
        return {"status": "error", "error": "Player already seated"}

    # Find seat
    preferred = request.get("preferred_seat")
    seat_index = None

    if preferred is not None:
        preferred = int(preferred)
        if preferred < 0 or preferred >= table.max_seats:
            return {"status": "error", "error": f"Invalid seat number: {preferred} (table has seats 0-{table.max_seats - 1})"}
        if table.seats[preferred] is not None:
            return {"status": "error", "error": f"Seat {preferred} is already taken"}
        seat_index = preferred

    if seat_index is None:
        for i in range(table.max_seats):
            if table.seats[i] is None:
                seat_index = i
                break

    if seat_index is None:
        return {"status": "error", "error": "Table is full"}

    seat = PlayerSeat(
        seat_index=seat_index,
        player_id=player_id,
        wallet_address=wallet_address,
        stack=buy_in,
    )
    table.seats[seat_index] = seat

    logger.info("Player %s joined table %s at seat %d (buy-in: %d)",
                player_id, table.table_id, seat_index, buy_in)

    return {
        "status": "ok",
        "seat_index": seat_index,
        "table_view": make_table_view(table, player_id),
    }


def _handle_leave_table(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table = _get_table(request, poker_tables)
    if isinstance(table, dict):
        return table

    player_id = request.get("player_id")
    seat = table.player_by_id(player_id)
    if seat is None:
        return {"status": "error", "error": "Player not at table"}

    # Can only leave between hands or if sitting out
    if table.hand is not None and not table.hand.hand_over and seat.is_active:
        return {"status": "error", "error": "Cannot leave during an active hand"}

    cashout_amount = seat.stack
    table.seats[seat.seat_index] = None

    logger.info("Player %s left table %s (cashout: %d)",
                player_id, table.table_id, cashout_amount)

    return {"status": "ok", "cashout_amount": cashout_amount}


def _handle_start_hand(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table = _get_table(request, poker_tables)
    if isinstance(table, dict):
        return table

    if table.hand is not None and not table.hand.hand_over:
        return {"status": "error", "error": "Hand already in progress"}

    # Initialize verification chain for this hand
    chain = SessionVerificationChain(session_id=f"{table.table_id}:hand")
    table.hand_verification = chain

    events, player_hands = start_hand(table)

    # Record verification events
    seated = [s.player_id for s in table.seated_players()]
    chain.record("hand_start", {
        "hand_number": table.hand.hand_number,
        "dealer_seat": table.hand.dealer_seat,
        "players": seated,
        "blinds": [table.small_blind, table.big_blind],
    }, f"Hand #{table.hand.hand_number} started with {len(seated)} players")

    chain.record("deck_shuffled", {
        "seed_hash": table.hand.deck_seed_hash,
    }, "Deck shuffled with CSPRNG inside TEE (seed sealed)")

    chain.record("hole_cards_dealt", {
        "player_count": len(player_hands),
    }, f"Hole cards dealt to {len(player_hands)} players")

    # Convert Card objects to dicts for JSON serialization
    serialized_hands: dict[str, list[dict]] = {}
    for pid, cards in player_hands.items():
        serialized_hands[pid] = [c.to_dict() for c in cards]

    return {
        "status": "ok",
        "hand_number": table.hand.hand_number,
        "events": events,
        "player_hands": serialized_hands,
    }


def _handle_player_action(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table = _get_table(request, poker_tables)
    if isinstance(table, dict):
        return table

    player_id = request.get("player_id")
    action_str = request.get("hand_action")
    amount = int(request.get("amount", 0))

    if not player_id or not action_str:
        return {"status": "error", "error": "Missing player_id or hand_action"}

    try:
        action = PlayerAction(action_str)
    except ValueError:
        return {"status": "error", "error": f"Invalid action: {action_str}"}

    events = process_action(table, player_id, action, amount)

    # Record verification event
    chain = table.hand_verification
    if chain:
        chain.record("player_action", {
            "player_id": player_id,
            "action": action_str,
            "amount": amount,
        }, f"Player {player_id[:8]}... {action_str}" + (f" {amount}" if amount else ""))

        # Record community card events
        for event in events:
            if event.get("type") == "community_cards":
                cards = event.get("cards", [])
                phase = event.get("phase", "")
                chain.record("community_cards", {
                    "phase": phase,
                    "card_count": len(cards),
                }, f"{phase.capitalize()}: {len(cards)} community card(s) revealed")

            if event.get("type") == "showdown":
                chain.record("showdown", {
                    "results": event.get("results", []),
                }, "Showdown: hands evaluated deterministically")

    response: dict[str, Any] = {
        "status": "ok",
        "events": events,
        "table_view": make_table_view(table, player_id),
    }

    # If hand is over, finalize verification and include it
    if table.hand and table.hand.hand_over:
        response["hand_over"] = True
        response["deck_seed_hash"] = table.hand.deck_seed_hash

        if chain:
            chain.record("hand_settled", {
                "deck_seed_hash": table.hand.deck_seed_hash,
            }, "Hand complete — deck seed hash published for verification")
            report = chain.finalize()
            response["verification"] = report.to_dict()
            table.hand_verification = None

    return response


def _handle_timeout(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table = _get_table(request, poker_tables)
    if isinstance(table, dict):
        return table

    seat_index = int(request.get("seat_index", -1))
    events = process_timeout(table, seat_index)

    # Record timeout as a player action in verification chain
    chain = table.hand_verification
    if chain:
        seat = table.seats[seat_index] if 0 <= seat_index < len(table.seats) else None
        pid = seat.player_id if seat else "unknown"
        chain.record("player_action", {
            "player_id": pid,
            "action": "timeout_fold",
            "seat_index": seat_index,
        }, f"Player {pid[:8]}... timed out (auto-fold)")

    response: dict[str, Any] = {
        "status": "ok",
        "events": events,
        "table_view": make_table_view(table),
    }

    # If hand ended due to timeout, finalize verification
    if table.hand and table.hand.hand_over and chain:
        response["hand_over"] = True
        response["deck_seed_hash"] = table.hand.deck_seed_hash
        chain.record("hand_settled", {
            "deck_seed_hash": table.hand.deck_seed_hash,
        }, "Hand complete — deck seed hash published for verification")
        report = chain.finalize()
        response["verification"] = report.to_dict()
        table.hand_verification = None

    return response


def _handle_get_table(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table = _get_table(request, poker_tables)
    if isinstance(table, dict):
        return table

    player_id = request.get("player_id")
    return {
        "status": "ok",
        "table_view": make_table_view(table, player_id),
    }


def _handle_rebuy(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> dict[str, Any]:
    table = _get_table(request, poker_tables)
    if isinstance(table, dict):
        return table

    player_id = request.get("player_id")
    amount = int(request.get("amount", 0))

    if not player_id:
        return {"status": "error", "error": "Missing player_id"}
    if amount <= 0:
        return {"status": "error", "error": "Rebuy amount must be positive"}

    seat = table.player_by_id(player_id)
    if seat is None:
        return {"status": "error", "error": "Player not at table"}

    # Only allow rebuy between hands
    if table.hand is not None and not table.hand.hand_over:
        return {"status": "error", "error": "Cannot rebuy during an active hand"}

    new_stack = seat.stack + amount
    if new_stack > table.max_buy_in:
        return {"status": "error", "error": f"Rebuy would exceed max buy-in ({table.max_buy_in})"}

    seat.stack = new_stack
    logger.info("Player %s rebuy %d at table %s (new stack: %d)",
                player_id, amount, table.table_id, new_stack)

    return {"status": "ok", "new_stack": new_stack}


def _get_table(
    request: dict[str, Any],
    poker_tables: dict[str, TableState],
) -> TableState | dict[str, Any]:
    """Get table by ID from request, or return an error response dict."""
    table_id = request.get("table_id")
    if not table_id:
        return {"status": "error", "error": "Missing table_id"}
    table = poker_tables.get(table_id)
    if table is None:
        return {"status": "error", "error": f"Table {table_id} not found"}
    return table
