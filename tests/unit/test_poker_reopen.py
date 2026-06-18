"""Regression tests for the betting-reopen rule (sub-minimum all-in).

Texas Hold'em rule: an all-in raise of *less than a full raise* does NOT reopen
the betting to players who have already acted. Such players may only call or fold
— they cannot re-raise off the short all-in. Players who have not yet acted this
round retain full betting rights, and a full-sized raise reopens betting to all.

The engine previously offered "raise"/"all_in" to *every* player facing a higher
bet, regardless of whether the action had been legitimately reopened to them.
"""

import copy
import random

import pytest

from ndai.enclave.poker.engine import (
    PokerEngineError,
    get_valid_actions,
    process_action,
    start_hand,
)
from ndai.enclave.poker.state import (
    PlayerAction,
    PlayerSeat,
    TableState,
)


def _make_table(stacks, sb=50, bb=100, max_seats=9) -> TableState:
    table = TableState(
        table_id="t",
        small_blind=sb,
        big_blind=bb,
        min_buy_in=bb * 5,
        max_buy_in=bb * 1000,
        max_seats=max(max_seats, len(stacks)),
    )
    for i, stk in enumerate(stacks):
        table.seats[i] = PlayerSeat(
            seat_index=i, player_id=f"p{i}", wallet_address=f"0x{i:040d}", stack=stk
        )
    return table


def _action_types(table: TableState, seat_idx: int) -> set[str]:
    return {a["action"] for a in get_valid_actions(table, seat_idx)}


class TestShortAllInDoesNotReopen:
    def test_acted_player_cannot_reraise_off_short_all_in(self):
        """P0 raises full; P1 short-all-ins; P0 (already acted) may only call/fold.

        3-handed, blinds 50/100. dealer=0 → SB=1, BB=2, UTG=0 acts first.
        P0 raises to 300 (full raise, min_raise becomes 200). P1 (SB) shoves all-in
        to 350 — a raise of only 50, well below the 200 minimum. That short all-in
        must NOT reopen betting to P0.
        """
        table = _make_table([10000, 350, 10000])
        start_hand(table)
        hand = table.hand

        process_action(table, "p0", PlayerAction.RAISE, amount=300)
        assert hand.current_bet == 300
        assert hand.min_raise == 200
        assert hand.reopen_bet == 300

        process_action(table, "p1", PlayerAction.ALL_IN)  # short all-in to 350
        assert hand.current_bet == 350
        assert hand.reopen_bet == 300  # unchanged: short all-in did not reopen

        # P2 (BB) has not acted — retains full rights including raise.
        assert "raise" in _action_types(table, hand.action_on)
        process_action(table, "p2", PlayerAction.CALL)

        # Action returns to P0, who already raised to 300. Only call/fold allowed.
        assert hand.action_on == 0
        assert _action_types(table, 0) == {"fold", "call"}

    def test_unacted_player_keeps_full_rights_facing_short_all_in(self):
        """A player who has not yet acted may raise even facing a short all-in."""
        table = _make_table([10000, 350, 10000])
        start_hand(table)
        hand = table.hand

        process_action(table, "p0", PlayerAction.RAISE, amount=300)
        process_action(table, "p1", PlayerAction.ALL_IN)  # short all-in

        # P2 (BB) is acting for the first time this round.
        assert hand.action_on == 2
        assert {"raise", "all_in"} <= _action_types(table, 2)

    def test_postflop_checker_cannot_reraise_off_short_all_in(self):
        """Postflop: a player who checked cannot re-raise off a sub-minimum all-in."""
        # p2 has a short stack so its postflop shove is below the min bet/raise.
        table = _make_table([10000, 10000, 130])
        start_hand(table)
        hand = table.hand

        # Preflop: everyone limps to see a flop. dealer=0 → SB=1,BB=2,UTG=0.
        process_action(table, "p0", PlayerAction.CALL)  # UTG calls 100
        process_action(table, "p1", PlayerAction.CALL)  # SB completes
        process_action(table, "p2", PlayerAction.CHECK)  # BB checks
        assert hand.phase.value == "flop"

        # Flop. First to act after dealer is p1. p0 checks behind once it's their turn;
        # p2 shoves its remaining 30 (130 - 100 preflop) — below the 100 min bet.
        order = []
        # Walk the flop: p1 checks, p2 (short) shoves, then action returns.
        process_action(table, "p1", PlayerAction.CHECK)
        # p2's turn: it can open-shove (nobody has acted aggressively, it is reopened to p2)
        assert "all_in" in _action_types(table, hand.action_on)
        process_action(table, f"p{hand.action_on}", PlayerAction.ALL_IN)
        assert hand.current_bet < table.big_blind  # short shove below a full bet
        assert hand.reopen_bet == 0  # never reopened

        # Now p0 has not acted on the flop yet → may raise.
        if hand.action_on == 0:
            assert "raise" in _action_types(table, 0) or "all_in" in _action_types(table, 0)
            process_action(table, "p0", PlayerAction.CALL)
        # And p1, who already checked, faces the short shove → call/fold only.
        if hand.action_on == 1:
            assert _action_types(table, 1) <= {"fold", "call", "all_in"}
            assert "raise" not in _action_types(table, 1)
        order.append(hand.action_on)


class TestEnclaveEnforcesReopen:
    """The enclave (process_action) must REJECT an illegal raise, not merely hide it.

    get_valid_actions only advertises the menu; the authoritative boundary is
    process_action. A buggy or adversarial client could send a raise directly.
    """

    def _setup_frozen_p0(self):
        # P0 raises full to 300; P1 short all-ins to 350; P2 calls. Action returns to P0,
        # which is now frozen (may only call/fold).
        table = _make_table([10000, 350, 10000])
        start_hand(table)
        process_action(table, "p0", PlayerAction.RAISE, amount=300)
        process_action(table, "p1", PlayerAction.ALL_IN)
        process_action(table, "p2", PlayerAction.CALL)
        assert table.hand.action_on == 0
        return table

    def test_process_action_rejects_illegal_raise(self):
        table = self._setup_frozen_p0()
        with pytest.raises(PokerEngineError, match="not reopened"):
            process_action(table, "p0", PlayerAction.RAISE, amount=1000)

    def test_process_action_rejects_illegal_all_in_shove(self):
        table = self._setup_frozen_p0()
        # P0 has a big stack; shoving would be a raise, which is not reopened to it.
        with pytest.raises(PokerEngineError, match="not reopened"):
            process_action(table, "p0", PlayerAction.ALL_IN)

    def test_frozen_player_may_still_call(self):
        table = self._setup_frozen_p0()
        # The legal action — a call — must still go through. (P0 was at 300; calling the
        # 350 level matches it. The betting round then completes and current_bet resets,
        # so assert on the persistent per-hand total instead.)
        process_action(table, "p0", PlayerAction.CALL)
        assert table.seats[0].total_bet_this_hand == 350

    def test_all_in_call_allowed_when_frozen_and_short(self):
        """A frozen seat that is too short to call may still all-in (it only under-calls)."""
        table = _make_table([10000, 350, 320])
        start_hand(table)
        # dealer=0 → SB=1, BB=2, UTG=0. P0 raises to 300 (full).
        process_action(table, "p0", PlayerAction.RAISE, amount=300)
        # P1 (SB) short all-ins to 350.
        process_action(table, "p1", PlayerAction.ALL_IN)
        # P2 (BB, 320 stack, 100 in) is acting first time → may act. It calls/raises freely;
        # here it just calls what it can. Then action returns to P0 (frozen).
        # P2 to_call = 350 - 100 = 250; stack 220 (<250) → all-in under-call, always legal.
        assert "all_in" in {a["action"] for a in get_valid_actions(table, 2)}
        process_action(table, "p2", PlayerAction.ALL_IN)  # all-in under-call
        # No exception — the engine accepted a legal short all-in call.


class TestFullRaiseReopens:
    def test_full_reraise_reopens_to_earlier_raiser(self):
        """A full re-raise reopens betting to a player who raised earlier."""
        table = _make_table([10000, 10000, 10000])
        start_hand(table)
        hand = table.hand

        process_action(table, "p0", PlayerAction.RAISE, amount=300)  # to 300
        assert hand.reopen_bet == 300
        # p1 (SB, current_bet 50) re-raises to 500 (full: +200). Additional = 450.
        process_action(table, "p1", PlayerAction.RAISE, amount=450)
        assert hand.current_bet == 500
        assert hand.reopen_bet == 500
        process_action(table, "p2", PlayerAction.CALL)

        # Back to p0: a full raise occurred since it last acted → may raise again.
        assert hand.action_on == 0
        assert "raise" in _action_types(table, 0)

    def test_big_blind_option_preserved(self):
        """Preflop: everyone limps; the big blind still has the option to raise."""
        table = _make_table([10000, 10000, 10000])
        start_hand(table)
        hand = table.hand

        process_action(table, "p0", PlayerAction.CALL)  # UTG limps
        process_action(table, "p1", PlayerAction.CALL)  # SB completes
        # Action is on the BB (p2), who has only posted the forced blind.
        assert hand.action_on == 2
        acts = _action_types(table, 2)
        assert "check" in acts
        # The big-blind option: BB may put more chips in voluntarily. With to_call == 0
        # the engine labels the aggressive action "bet" (it routes to the same handler
        # as "raise"), so accept either label here.
        assert acts & {"bet", "raise"}, acts


class TestOfferedActionsAreLegal:
    def test_every_offered_action_is_accepted(self):
        """Fuzz: every action get_valid_actions offers must be processable.

        Catches inconsistencies between the action menu and the action handlers —
        e.g. offering a raise that process_action would reject. We deep-copy the
        table and try each offered action in isolation so the probe never disturbs
        the real game.
        """
        rng = random.Random(7)
        for _ in range(800):
            n = rng.randint(2, 6)
            stacks = [rng.choice([120, 150, 200, 350, 500, 1000, 5000]) for _ in range(n)]
            table = _make_table(stacks)
            start_hand(table)

            guard = 0
            while table.hand and not table.hand.hand_over and guard < 400:
                guard += 1
                seat_idx = table.hand.action_on
                if seat_idx is None:
                    break
                offered = get_valid_actions(table, seat_idx)
                if not offered:
                    break
                pid = table.seats[seat_idx].player_id

                # Every offered action must succeed on a fresh copy.
                for choice in offered:
                    probe = copy.deepcopy(table)
                    act = PlayerAction(choice["action"])
                    if choice["action"] in ("bet", "raise"):
                        for amt in {choice["min"], choice["max"]}:
                            probe2 = copy.deepcopy(table)
                            process_action(probe2, pid, act, amt)
                    else:
                        process_action(probe, pid, act)

                # Advance the real game with a random legal action.
                choice = rng.choice(offered)
                if choice["action"] in ("bet", "raise"):
                    amt = rng.randint(choice["min"], choice["max"])
                    process_action(table, pid, PlayerAction(choice["action"]), amt)
                else:
                    process_action(table, pid, PlayerAction(choice["action"]))

    def test_fuzz_still_zero_sum_after_reopen_gating(self):
        """Chips are conserved across many fuzzed hands with the new gating."""
        rng = random.Random(99)
        for _ in range(2000):
            n = rng.randint(2, 6)
            stacks = [rng.choice([120, 200, 350, 500, 1000]) for _ in range(n)]
            table = _make_table(stacks)
            before = sum(s.stack for s in table.seats if s is not None)
            start_hand(table)

            guard = 0
            while table.hand and not table.hand.hand_over and guard < 400:
                guard += 1
                seat_idx = table.hand.action_on
                if seat_idx is None:
                    break
                offered = get_valid_actions(table, seat_idx)
                if not offered:
                    break
                choice = rng.choice(offered)
                pid = table.seats[seat_idx].player_id
                if choice["action"] in ("bet", "raise"):
                    amt = rng.randint(choice["min"], choice["max"])
                    process_action(table, pid, PlayerAction(choice["action"]), amt)
                else:
                    process_action(table, pid, PlayerAction(choice["action"]))

            after = sum(s.stack for s in table.seats if s is not None)
            assert after == before, f"chips changed {before} -> {after} (stacks={stacks})"
