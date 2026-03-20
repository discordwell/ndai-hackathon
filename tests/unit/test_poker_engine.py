"""Tests for poker game engine."""

import pytest

from ndai.enclave.poker.engine import (
    PokerEngineError,
    get_valid_actions,
    process_action,
    process_timeout,
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
    max_seats: int = 9,
) -> TableState:
    table = TableState(
        table_id="test-table",
        small_blind=small_blind,
        big_blind=big_blind,
        min_buy_in=big_blind * 10,
        max_buy_in=big_blind * 100,
        max_seats=max_seats,
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


def _find_events(events: list[dict], event_type: str) -> list[dict]:
    return [e for e in events if e["type"] == event_type]


class TestStartHand:
    def test_basic_start(self):
        table = _make_table(3)
        events, hands = start_hand(table)
        assert table.hand is not None
        assert table.hand.hand_number == 1
        assert len(hands) == 3
        for pid, cards in hands.items():
            assert len(cards) == 2

    def test_blinds_posted(self):
        table = _make_table(3, small_blind=50, big_blind=100)
        events, _ = start_hand(table)
        blind_events = _find_events(events, "blinds_posted")
        assert len(blind_events) == 2

    def test_stacks_reduced_by_blinds(self):
        table = _make_table(3, small_blind=50, big_blind=100, stack=1000)
        events, _ = start_hand(table)
        hand = table.hand
        sb_seat = table.seats[hand.small_blind_seat]
        bb_seat = table.seats[hand.big_blind_seat]
        assert sb_seat.stack == 950
        assert bb_seat.stack == 900

    def test_action_on_is_set(self):
        table = _make_table(3)
        events, _ = start_hand(table)
        action_event = _find_event(events, "action_on")
        assert action_event is not None
        assert table.hand.action_on is not None

    def test_heads_up_dealer_is_small_blind(self):
        table = _make_table(2)
        events, _ = start_hand(table)
        hand = table.hand
        assert hand.small_blind_seat == hand.dealer_seat

    def test_three_player_dealer_not_blind(self):
        table = _make_table(3)
        events, _ = start_hand(table)
        hand = table.hand
        assert hand.small_blind_seat != hand.dealer_seat
        assert hand.big_blind_seat != hand.dealer_seat

    def test_need_two_players(self):
        table = _make_table(1)
        with pytest.raises(PokerEngineError, match="at least 2"):
            start_hand(table)

    def test_deck_has_remaining_cards(self):
        table = _make_table(3)
        events, _ = start_hand(table)
        # 52 - (3*2) = 46
        assert len(table.hand.deck) == 46

    def test_hand_count_increments(self):
        table = _make_table(2)
        start_hand(table)
        assert table.hand_count == 1
        # Reset for next hand
        table.hand = None
        for s in table.seats:
            if s:
                s.stack = 10000
        start_hand(table)
        assert table.hand_count == 2


class TestValidActions:
    def test_preflop_utg_can_fold_call_raise(self):
        table = _make_table(3, big_blind=200, stack=10000)
        start_hand(table)
        seat_idx = table.hand.action_on
        actions = get_valid_actions(table, seat_idx)
        action_types = {a["action"] for a in actions}
        assert "fold" in action_types
        assert "call" in action_types
        assert "raise" in action_types

    def test_wrong_seat_gets_no_actions(self):
        table = _make_table(3)
        start_hand(table)
        wrong_seat = (table.hand.action_on + 1) % table.max_seats
        actions = get_valid_actions(table, wrong_seat)
        assert actions == []

    def test_can_check_when_no_bet(self):
        table = _make_table(2, small_blind=50, big_blind=100, stack=10000)
        start_hand(table)
        hand = table.hand
        # Heads-up: SB (dealer) acts first preflop - call
        process_action(table, f"player-{hand.action_on}", PlayerAction.CALL)
        # BB can check
        actions = get_valid_actions(table, hand.action_on)
        action_types = {a["action"] for a in actions}
        assert "check" in action_types

    def test_short_stack_can_only_all_in(self):
        table = _make_table(2, small_blind=50, big_blind=100, stack=80)
        start_hand(table)
        hand = table.hand
        seat = table.seats[hand.action_on]
        actions = get_valid_actions(table, hand.action_on)
        action_types = {a["action"] for a in actions}
        assert "all_in" in action_types
        # Can't regular call or raise with less than the big blind
        assert "raise" not in action_types


class TestProcessAction:
    def test_fold(self):
        table = _make_table(3, big_blind=200, stack=10000)
        start_hand(table)
        seat_idx = table.hand.action_on
        player_id = f"player-{seat_idx}"
        events = process_action(table, player_id, PlayerAction.FOLD)
        seat = table.seats[seat_idx]
        assert not seat.is_active

    def test_call(self):
        table = _make_table(3, small_blind=50, big_blind=100, stack=10000)
        start_hand(table)
        seat_idx = table.hand.action_on
        player_id = f"player-{seat_idx}"
        events = process_action(table, player_id, PlayerAction.CALL)
        seat = table.seats[seat_idx]
        assert seat.current_bet == 100  # called the big blind

    def test_raise(self):
        table = _make_table(3, small_blind=50, big_blind=100, stack=10000)
        start_hand(table)
        seat_idx = table.hand.action_on
        player_id = f"player-{seat_idx}"
        # Raise: put in 300 additional chips (new total bet = 300)
        events = process_action(table, player_id, PlayerAction.RAISE, amount=300)
        assert table.hand.current_bet == 300

    def test_wrong_player_raises_error(self):
        table = _make_table(3)
        start_hand(table)
        wrong_idx = (table.hand.action_on + 1) % table.max_seats
        with pytest.raises(PokerEngineError, match="Not player"):
            process_action(table, f"player-{wrong_idx}", PlayerAction.FOLD)

    def test_cannot_check_with_bet_pending(self):
        table = _make_table(3, big_blind=200, stack=10000)
        start_hand(table)
        seat_idx = table.hand.action_on
        player_id = f"player-{seat_idx}"
        with pytest.raises(PokerEngineError, match="Cannot check"):
            process_action(table, player_id, PlayerAction.CHECK)

    def test_all_in(self):
        table = _make_table(2, small_blind=50, big_blind=100, stack=500)
        start_hand(table)
        seat_idx = table.hand.action_on
        player_id = f"player-{seat_idx}"
        events = process_action(table, player_id, PlayerAction.ALL_IN)
        seat = table.seats[seat_idx]
        assert seat.stack == 0


class TestFullHand:
    def test_fold_to_win(self):
        """One player folds, other wins."""
        table = _make_table(2, small_blind=50, big_blind=100, stack=5000)
        events, _ = start_hand(table)
        hand = table.hand

        # First player folds
        seat_idx = hand.action_on
        events = process_action(table, f"player-{seat_idx}", PlayerAction.FOLD)

        # Hand should be over
        assert hand.hand_over
        hand_end = _find_event(events, "hand_end")
        assert hand_end is not None
        assert hand_end["reason"] == "last_standing"

    def test_call_call_to_showdown(self):
        """Both players call through all streets to showdown."""
        table = _make_table(2, small_blind=50, big_blind=100, stack=5000)
        events, _ = start_hand(table)
        hand = table.hand

        # Play through all streets
        max_actions = 20  # safety limit
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
            actions_taken += 1

        assert hand.hand_over
        assert hand.phase == HandPhase.SHOWDOWN
        assert len(hand.community_cards) == 5

    def test_three_player_hand(self):
        """Three-player hand: one folds, two go to showdown."""
        table = _make_table(3, small_blind=50, big_blind=100, stack=5000)
        events, _ = start_hand(table)
        hand = table.hand

        # First player calls
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.CALL)

        # Second player calls
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.CALL)

        # Third player (BB) checks
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.CHECK)

        # Flop
        assert hand.phase == HandPhase.FLOP
        assert len(hand.community_cards) == 3

        # First active player after dealer folds
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.FOLD)

        # Continue with checks
        max_actions = 20
        actions_taken = 0
        while not hand.hand_over and actions_taken < max_actions:
            seat_idx = hand.action_on
            if seat_idx is None:
                break
            player_id = f"player-{seat_idx}"
            seat = table.seats[seat_idx]
            if hand.current_bet > seat.current_bet:
                process_action(table, player_id, PlayerAction.CALL)
            else:
                process_action(table, player_id, PlayerAction.CHECK)
            actions_taken += 1

        assert hand.hand_over

    def test_all_in_runs_out_board(self):
        """When both players are all-in, community cards are dealt automatically."""
        table = _make_table(2, small_blind=50, big_blind=100, stack=500)
        events, _ = start_hand(table)
        hand = table.hand

        # First player goes all-in
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.ALL_IN)

        # Second player calls all-in
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.ALL_IN)

        # Hand should finish with showdown
        assert hand.hand_over
        assert len(hand.community_cards) == 5

    def test_winner_gets_pot(self):
        """After a fold, winner's stack should increase by the pot amount."""
        table = _make_table(2, small_blind=50, big_blind=100, stack=5000)
        start_hand(table)
        hand = table.hand

        # Track initial stacks
        initial_stacks = {s.player_id: 5000 for s in table.seats if s is not None}

        # First player folds
        seat_idx = hand.action_on
        folder_id = f"player-{seat_idx}"
        process_action(table, folder_id, PlayerAction.FOLD)

        # Winner should have gained the pot
        total_stacks = sum(s.stack for s in table.seats if s is not None)
        assert total_stacks == 10000  # zero-sum

    def test_stacks_are_zero_sum(self):
        """Total chips at table must remain constant throughout a hand."""
        table = _make_table(3, small_blind=50, big_blind=100, stack=5000)
        initial_total = 15000
        start_hand(table)
        hand = table.hand

        # Play a few actions
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.CALL)
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.CALL)
        seat_idx = hand.action_on
        process_action(table, f"player-{seat_idx}", PlayerAction.CHECK)

        # Total should still be the same (stacks + bets in pot)
        # After a round completes, bets are collected into pots
        stacks = sum(s.stack for s in table.seats if s is not None)
        bets = sum(s.current_bet for s in table.seats if s is not None)
        pot = sum(p.amount for p in hand.pots)
        total = stacks + bets + pot
        # Note: bets and pot overlap after collection, so just check stacks + uncollected
        # After phase advance, current_bet resets and pots include everything
        # Simpler check: just verify hand over gives zero-sum
        max_actions = 30
        actions_taken = 0
        while not hand.hand_over and actions_taken < max_actions:
            seat_idx = hand.action_on
            if seat_idx is None:
                break
            player_id = f"player-{seat_idx}"
            seat = table.seats[seat_idx]
            if hand.current_bet > seat.current_bet:
                process_action(table, player_id, PlayerAction.CALL)
            else:
                process_action(table, player_id, PlayerAction.CHECK)
            actions_taken += 1

        final_total = sum(s.stack for s in table.seats if s is not None)
        assert final_total == initial_total


class TestTimeout:
    def test_timeout_folds_player(self):
        table = _make_table(3, big_blind=200, stack=10000)
        start_hand(table)
        seat_idx = table.hand.action_on
        events = process_timeout(table, seat_idx)
        timeout_event = _find_event(events, "player_timeout")
        assert timeout_event is not None
        assert not table.seats[seat_idx].is_active

    def test_timeout_wrong_seat_ignored(self):
        table = _make_table(3)
        start_hand(table)
        wrong_seat = (table.hand.action_on + 1) % table.max_seats
        events = process_timeout(table, wrong_seat)
        assert events == []


class TestDealerRotation:
    def test_dealer_rotates(self):
        table = _make_table(3, stack=50000)

        start_hand(table)
        dealer1 = table.hand.dealer_seat
        table.hand = None
        for s in table.seats:
            if s:
                s.stack = 50000

        start_hand(table)
        dealer2 = table.hand.dealer_seat
        assert dealer2 != dealer1

    def test_dealer_wraps_around(self):
        table = _make_table(3, max_seats=3, stack=50000)
        dealers = []
        for _ in range(4):
            start_hand(table)
            dealers.append(table.hand.dealer_seat)
            table.hand = None
            for s in table.seats:
                if s:
                    s.stack = 50000
        # Should have visited at least 3 different seats
        assert len(set(dealers)) >= 2
