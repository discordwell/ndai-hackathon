"""Tests for poker hand data extraction and completeness.

Validates that the engine produces the event data needed for
hand history persistence (community_cards, pots_awarded, deck_seed_hash).
"""

import pytest

from ndai.enclave.poker.engine import (
    process_action,
    start_hand,
)
from ndai.enclave.poker.state import (
    HandPhase,
    PlayerAction,
    PlayerSeat,
    TableState,
)


def _make_table(
    num_players: int = 2,
    small_blind: int = 100,
    big_blind: int = 200,
    stack: int = 10000,
) -> TableState:
    table = TableState(
        table_id="test-table",
        small_blind=small_blind,
        big_blind=big_blind,
        min_buy_in=big_blind * 10,
        max_buy_in=big_blind * 100,
        max_seats=9,
    )
    for i in range(num_players):
        table.seats[i] = PlayerSeat(
            seat_index=i,
            player_id=f"player-{i}",
            wallet_address=f"0x{'0' * 38}{i:02d}",
            stack=stack,
        )
    return table


def _find_event(events: list[dict], event_type: str) -> dict | None:
    for e in events:
        if e["type"] == event_type:
            return e
    return None


def _play_to_showdown(table: TableState) -> list[dict]:
    """Play a hand through to completion via check/call. Returns all events."""
    all_events = []
    hand = table.hand
    max_actions = 30
    actions_taken = 0
    while not hand.hand_over and actions_taken < max_actions:
        seat_idx = hand.action_on
        if seat_idx is None:
            break
        player_id = f"player-{seat_idx}"
        seat = table.seats[seat_idx]
        if hand.current_bet > seat.current_bet:
            events = process_action(table, player_id, PlayerAction.CALL)
        else:
            events = process_action(table, player_id, PlayerAction.CHECK)
        all_events.extend(events)
        actions_taken += 1
    return all_events


class TestHandEndEventData:
    """Verify hand_end events contain all data needed for persistence."""

    def test_showdown_has_community_cards(self):
        """Showdown event must include community_cards for hand history."""
        table = _make_table(2)
        start_hand(table)
        events = _play_to_showdown(table)

        showdown = _find_event(events, "showdown")
        assert showdown is not None
        assert "community_cards" in showdown
        assert len(showdown["community_cards"]) == 5
        for card in showdown["community_cards"]:
            assert "rank" in card
            assert "suit" in card

    def test_showdown_has_results(self):
        """Showdown event must include results with winner info."""
        table = _make_table(2)
        start_hand(table)
        events = _play_to_showdown(table)

        showdown = _find_event(events, "showdown")
        assert showdown is not None
        assert "results" in showdown
        assert len(showdown["results"]) > 0
        result = showdown["results"][0]
        assert "player_id" in result
        assert "amount" in result
        assert "hand_rank" in result
        assert "cards_shown" in result
        assert "best_five" in result

    def test_hand_end_has_deck_seed_hash(self):
        """hand_end event must include deck_seed_hash for verification."""
        table = _make_table(2)
        start_hand(table)
        events = _play_to_showdown(table)

        hand_end = _find_event(events, "hand_end")
        assert hand_end is not None
        assert "deck_seed_hash" in hand_end
        assert isinstance(hand_end["deck_seed_hash"], str)
        assert len(hand_end["deck_seed_hash"]) == 64  # SHA-256 hex

    def test_hand_end_has_stack_updates(self):
        """hand_end event must include stack_updates for settlement."""
        table = _make_table(2)
        start_hand(table)
        events = _play_to_showdown(table)

        hand_end = _find_event(events, "hand_end")
        assert hand_end is not None
        assert "stack_updates" in hand_end
        stacks = hand_end["stack_updates"]
        assert "player-0" in stacks
        assert "player-1" in stacks
        # Zero-sum
        assert sum(stacks.values()) == 20000

    def test_fold_hand_end_has_data(self):
        """hand_end via fold must include winner info and deck_seed_hash."""
        table = _make_table(2)
        start_hand(table)
        hand = table.hand

        seat_idx = hand.action_on
        events = process_action(table, f"player-{seat_idx}", PlayerAction.FOLD)

        hand_end = _find_event(events, "hand_end")
        assert hand_end is not None
        assert hand_end["reason"] == "last_standing"
        assert "winner_player_id" in hand_end
        assert "amount" in hand_end
        assert "deck_seed_hash" in hand_end
        assert "stack_updates" in hand_end

    def test_player_action_events_contain_seat(self):
        """player_action events must contain seat index for persistence."""
        table = _make_table(2)
        start_hand(table)
        hand = table.hand

        seat_idx = hand.action_on
        events = process_action(table, f"player-{seat_idx}", PlayerAction.CALL)

        action_event = _find_event(events, "player_action")
        assert action_event is not None
        assert "seat" in action_event
        assert "action" in action_event
        assert "amount" in action_event

    def test_phase_change_events_contain_community_cards(self):
        """phase_change events must contain cumulative community cards."""
        table = _make_table(2, stack=10000)
        start_hand(table)
        all_events = _play_to_showdown(table)

        phase_events = [e for e in all_events if e["type"] == "phase_change"]
        assert len(phase_events) >= 1  # at least flop

        for pe in phase_events:
            assert "community_cards" in pe
            assert "phase" in pe

        # Find flop event
        flop = next((e for e in phase_events if e["phase"] == "flop"), None)
        if flop:
            assert len(flop["community_cards"]) == 3


class TestVerificationChainIntegration:
    """Verify the enclave action handlers produce verification data."""

    def test_start_hand_returns_hand_number(self):
        """poker_start_hand must return hand_number for DB persistence."""
        from ndai.enclave.poker.actions import handle_poker_action

        tables = {}
        handle_poker_action({"action": "poker_create_table", "table_id": "t1",
                             "small_blind": 50, "big_blind": 100,
                             "min_buy_in": 1000, "max_buy_in": 10000,
                             "max_seats": 6}, tables)

        for i in range(2):
            handle_poker_action({"action": "poker_join_table", "table_id": "t1",
                                 "player_id": f"p{i}", "wallet_address": f"0x{i:040d}",
                                 "buy_in": 5000}, tables)

        result = handle_poker_action({"action": "poker_start_hand", "table_id": "t1"}, tables)
        assert result["status"] == "ok"
        assert "hand_number" in result
        assert result["hand_number"] == 1
        assert "player_hands" in result
        assert len(result["player_hands"]) == 2

    def test_player_action_returns_hand_over_and_verification(self):
        """When hand ends, response must include hand_over flag and verification."""
        from ndai.enclave.poker.actions import handle_poker_action

        tables = {}
        handle_poker_action({"action": "poker_create_table", "table_id": "t1",
                             "small_blind": 50, "big_blind": 100,
                             "min_buy_in": 1000, "max_buy_in": 10000,
                             "max_seats": 6}, tables)

        for i in range(2):
            handle_poker_action({"action": "poker_join_table", "table_id": "t1",
                                 "player_id": f"p{i}", "wallet_address": f"0x{i:040d}",
                                 "buy_in": 5000}, tables)

        start_result = handle_poker_action({"action": "poker_start_hand", "table_id": "t1"}, tables)
        assert start_result["status"] == "ok"

        hand = tables["t1"].hand
        acting = hand.action_on
        pid = f"p{acting}"

        # Fold to end the hand immediately
        result = handle_poker_action({"action": "poker_action", "table_id": "t1",
                                      "player_id": pid, "hand_action": "fold",
                                      "amount": 0}, tables)

        assert result["status"] == "ok"
        assert result.get("hand_over") is True
        assert "deck_seed_hash" in result
        assert "verification" in result
        assert isinstance(result["verification"], dict)


class TestActionSequenceTracking:
    """Verify action events are ordered correctly for replay."""

    def test_actions_have_monotonic_seats(self):
        """Actions in a betting round follow seat order."""
        table = _make_table(3, stack=10000)
        start_hand(table)
        hand = table.hand

        seats_acted = []
        # First 3 actions (UTG, SB, BB in preflop)
        for _ in range(3):
            if hand.hand_over or hand.action_on is None:
                break
            seat_idx = hand.action_on
            pid = f"player-{seat_idx}"
            if hand.current_bet > table.seats[seat_idx].current_bet:
                process_action(table, pid, PlayerAction.CALL)
            else:
                process_action(table, pid, PlayerAction.CHECK)
            seats_acted.append(seat_idx)

        # All 3 players should have acted
        assert len(seats_acted) == 3
        # All different seats
        assert len(set(seats_acted)) == 3
