"""Regression tests for chip conservation (zero-sum) at hand resolution.

A side pot built above the highest active all-in level can be funded entirely by
folded over-bettors, leaving it with no eligible winner. `_showdown` previously
dropped such pots, destroying those chips. `_return_uncalled_bets` now returns
the uncalled excess to its contributors before pots are built.
"""

import random

from ndai.enclave.poker.engine import (
    _collect_bets_into_pots,
    _return_uncalled_bets,
    get_valid_actions,
    process_action,
    start_hand,
)
from ndai.enclave.poker.state import (
    HandState,
    PlayerAction,
    PlayerSeat,
    TableState,
)


def _make_table(stacks, sb=10, bb=20) -> TableState:
    table = TableState(
        table_id="t",
        small_blind=sb,
        big_blind=bb,
        min_buy_in=bb * 5,
        max_buy_in=bb * 1000,
        max_seats=max(9, len(stacks)),
    )
    for i, stk in enumerate(stacks):
        table.seats[i] = PlayerSeat(
            seat_index=i, player_id=f"p{i}", wallet_address=f"0x{i:040d}", stack=stk
        )
    return table


class TestUncalledBetReturn:
    def test_overbet_above_active_allins_returned_to_folders(self):
        """Two folded players over-bet beyond the highest active all-in.

        Active: p0 all-in at 60, p3 all-in at 100. Folded: p1, p2 at 197 each.
        The chips above 100 (97 from each folder = 194) are uncalled and must be
        returned, not parked in a dead side pot.
        """
        table = _make_table([1000, 1000, 1000, 1000])
        table.hand = HandState(hand_number=1)

        layout = {
            0: (60, True, 0),  # active all-in
            3: (100, True, 0),  # active all-in
            1: (197, False, 803),  # folded
            2: (197, False, 803),  # folded
        }
        chips_total = 0
        for idx, (total_bet, active, stack) in layout.items():
            seat = table.seats[idx]
            seat.total_bet_this_hand = total_bet
            seat.is_active = active
            seat.stack = stack
            chips_total += total_bet + stack

        returned = _return_uncalled_bets(table)

        # Each folder gets the 97 uncalled excess back; their wager caps at 100.
        assert table.seats[1].stack == 900
        assert table.seats[2].stack == 900
        assert table.seats[1].total_bet_this_hand == 100
        assert table.seats[2].total_bet_this_hand == 100
        # Active all-in players are never refunded.
        assert table.seats[0].total_bet_this_hand == 60
        assert table.seats[3].total_bet_this_hand == 100
        assert {e["seat"] for e in returned} == {1, 2}
        assert all(e["amount"] == 97 for e in returned)

        # No dead pot remains, and chips are conserved.
        _collect_bets_into_pots(table)
        for pot in table.hand.pots:
            if pot.amount > 0:
                assert pot.eligible_players, "pot with money must have an eligible winner"
        in_pots = sum(p.amount for p in table.hand.pots)
        in_stacks = sum(s.stack for s in table.seats if s is not None)
        assert in_pots + in_stacks == chips_total

    def test_no_refund_when_bets_are_matched(self):
        """When every wager is matched by an active player, nothing is returned."""
        table = _make_table([1000, 1000, 1000])
        table.hand = HandState(hand_number=1)
        for idx in (0, 1, 2):
            table.seats[idx].total_bet_this_hand = 100
            table.seats[idx].stack = 900
        assert _return_uncalled_bets(table) == []
        assert all(table.seats[i].total_bet_this_hand == 100 for i in (0, 1, 2))


class TestZeroSumInvariant:
    def test_random_hands_conserve_chips(self):
        """Fuzz many full hands; total chips must never change across a hand."""
        rng = random.Random(2024)
        for _ in range(2000):
            n = rng.randint(3, 6)
            stacks = [rng.choice([40, 55, 60, 80, 100, 200, 500, 1000]) for _ in range(n)]
            table = _make_table(stacks)
            before = sum(s.stack for s in table.seats if s is not None)
            start_hand(table)

            guard = 0
            while table.hand and not table.hand.hand_over and guard < 400:
                guard += 1
                seat_idx = table.hand.action_on
                if seat_idx is None:
                    break
                actions = get_valid_actions(table, seat_idx)
                if not actions:
                    break
                choice = rng.choice(actions)
                pid = table.seats[seat_idx].player_id
                if choice["action"] in ("bet", "raise"):
                    amt = rng.randint(choice["min"], choice["max"])
                    process_action(table, pid, PlayerAction(choice["action"]), amt)
                else:
                    process_action(table, pid, PlayerAction(choice["action"]))

            after = sum(s.stack for s in table.seats if s is not None)
            assert after == before, f"chips changed {before} -> {after} (stacks={stacks})"
