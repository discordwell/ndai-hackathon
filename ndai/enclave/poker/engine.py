"""Poker game engine — state machine for Texas Hold'em.

Handles blinds, dealing, betting rounds, side pots, and showdown.
All state mutations happen here. Pure logic, no I/O.
"""

from __future__ import annotations

import time
from typing import Any

from ndai.enclave.poker.deck import deal, shuffle_deck
from ndai.enclave.poker.evaluator import evaluate_hand, best_hand_cards
from ndai.enclave.poker.state import (
    Card,
    HandPhase,
    HandState,
    PlayerAction,
    PlayerSeat,
    Pot,
    TableState,
)


class PokerEngineError(Exception):
    """Raised when an invalid game action is attempted."""


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def _event(event_type: str, **data: Any) -> dict[str, Any]:
    return {"type": event_type, **data}


# ---------------------------------------------------------------------------
# Hand lifecycle
# ---------------------------------------------------------------------------

def start_hand(table: TableState) -> tuple[list[dict], dict[str, list[Card]]]:
    """Start a new hand: shuffle, post blinds, deal hole cards.

    Returns (events, player_hands) where player_hands maps player_id -> [Card, Card].
    """
    players = table.seated_players()
    if len(players) < 2:
        raise PokerEngineError("Need at least 2 players to start a hand")

    table.hand_count += 1

    # Rotate dealer
    if table.hand_count > 1:
        table.dealer_seat = table.next_occupied_seat(table.dealer_seat)
    else:
        # First hand — dealer is the first occupied seat
        for i in range(table.max_seats):
            if table.seats[i] is not None and not table.seats[i].is_sitting_out:
                table.dealer_seat = i
                break

    # Shuffle deck
    deck, seed, seed_hash = shuffle_deck()

    # Create hand state
    hand = HandState(
        hand_number=table.hand_count,
        deck=deck,
        deck_seed=seed,
        deck_seed_hash=seed_hash,
        dealer_seat=table.dealer_seat,
    )
    table.hand = hand

    # Reset player state for new hand
    for seat in table.seats:
        if seat is not None and not seat.is_sitting_out:
            seat.is_active = True
            seat.hole_cards = []
            seat.current_bet = 0
            seat.has_acted = False
            seat.total_bet_this_hand = 0

    events: list[dict] = []

    # Determine blind positions
    num_players = len(players)
    if num_players == 2:
        # Heads-up: dealer is small blind, other is big blind
        hand.small_blind_seat = table.dealer_seat
        hand.big_blind_seat = table.next_occupied_seat(table.dealer_seat)
    else:
        hand.small_blind_seat = table.next_occupied_seat(table.dealer_seat)
        hand.big_blind_seat = table.next_occupied_seat(hand.small_blind_seat)

    events.append(_event("hand_start", hand_number=hand.hand_number, dealer_seat=hand.dealer_seat))

    # Post blinds
    sb_events = _post_blind(table, hand.small_blind_seat, table.small_blind, "small_blind")
    bb_events = _post_blind(table, hand.big_blind_seat, table.big_blind, "big_blind")
    events.extend(sb_events)
    events.extend(bb_events)

    hand.current_bet = table.big_blind
    hand.min_raise = table.big_blind
    hand.last_raise_size = table.big_blind

    # Deal hole cards
    player_hands: dict[str, list[Card]] = {}
    for seat in table.seats:
        if seat is not None and seat.is_active:
            cards = deal(hand.deck, 2)
            seat.hole_cards = cards
            player_hands[seat.player_id] = cards

    events.append(_event("cards_dealt", seat_count=len(player_hands)))

    # Set action to first player after big blind
    if num_players == 2:
        # Heads-up preflop: small blind (dealer) acts first
        hand.action_on = hand.small_blind_seat
    else:
        hand.action_on = table.next_occupied_seat(hand.big_blind_seat)
        # Skip players who are all-in from the blinds
        _skip_all_in_players(table)

    timeout_at = time.time() + table.action_timeout_sec
    events.append(_event("action_on", seat=hand.action_on, timeout_at=timeout_at))

    # Initialize main pot
    hand.pots = [Pot(amount=0, eligible_players=[s.player_id for s in players])]

    return events, player_hands


def _post_blind(table: TableState, seat_idx: int, amount: int, blind_type: str) -> list[dict]:
    """Post a blind, handling case where player doesn't have enough (all-in)."""
    seat = table.seats[seat_idx]
    if seat is None:
        return []

    actual = min(amount, seat.stack)
    seat.stack -= actual
    seat.current_bet = actual
    seat.total_bet_this_hand = actual

    return [_event("blinds_posted", seat=seat_idx, blind_type=blind_type, amount=actual)]


def _skip_all_in_players(table: TableState) -> None:
    """Advance action_on past all-in players."""
    hand = table.hand
    if hand is None or hand.action_on is None:
        return
    start = hand.action_on
    for _ in range(table.max_seats):
        seat = table.seats[hand.action_on]
        if seat is not None and seat.is_active and seat.stack > 0:
            return
        next_seat = table.next_active_seat(hand.action_on)
        if next_seat is None or next_seat == start:
            hand.action_on = None
            return
        hand.action_on = next_seat


# ---------------------------------------------------------------------------
# Player actions
# ---------------------------------------------------------------------------

def get_valid_actions(table: TableState, seat_idx: int) -> list[dict[str, Any]]:
    """Return valid actions for the given seat."""
    hand = table.hand
    if hand is None or hand.action_on != seat_idx:
        return []

    seat = table.seats[seat_idx]
    if seat is None or not seat.is_active:
        return []

    actions: list[dict[str, Any]] = []
    to_call = hand.current_bet - seat.current_bet

    # Fold is always available
    actions.append({"action": "fold"})

    if to_call <= 0:
        # No bet to call — can check or bet
        actions.append({"action": "check"})
        if seat.stack > 0:
            min_bet = table.big_blind
            if seat.stack <= min_bet:
                actions.append({"action": "all_in", "amount": seat.stack})
            else:
                actions.append({"action": "bet", "min": min_bet, "max": seat.stack})
                actions.append({"action": "all_in", "amount": seat.stack})
    else:
        # There's a bet to call
        if seat.stack <= to_call:
            # Can only call all-in
            actions.append({"action": "all_in", "amount": seat.stack})
        else:
            actions.append({"action": "call", "amount": to_call})
            min_raise_total = hand.current_bet + hand.min_raise
            raise_cost = min_raise_total - seat.current_bet
            if seat.stack <= raise_cost:
                actions.append({"action": "all_in", "amount": seat.stack})
            else:
                actions.append({
                    "action": "raise",
                    "min": raise_cost,
                    "max": seat.stack,
                })
                actions.append({"action": "all_in", "amount": seat.stack})

    return actions


def process_action(
    table: TableState, player_id: str, action: PlayerAction, amount: int = 0
) -> list[dict]:
    """Process a player action. Returns list of events."""
    hand = table.hand
    if hand is None or hand.hand_over:
        raise PokerEngineError("No active hand")

    seat = table.player_by_id(player_id)
    if seat is None:
        raise PokerEngineError(f"Player {player_id} not at table")
    if hand.action_on != seat.seat_index:
        raise PokerEngineError(f"Not player {player_id}'s turn (action_on={hand.action_on})")
    if not seat.is_active:
        raise PokerEngineError("Player has already folded")

    events: list[dict] = []

    if action == PlayerAction.FOLD:
        events.extend(_do_fold(table, seat))
    elif action == PlayerAction.CHECK:
        events.extend(_do_check(table, seat))
    elif action == PlayerAction.CALL:
        events.extend(_do_call(table, seat))
    elif action in (PlayerAction.BET, PlayerAction.RAISE):
        events.extend(_do_raise(table, seat, amount))
    elif action == PlayerAction.ALL_IN:
        events.extend(_do_all_in(table, seat))
    else:
        raise PokerEngineError(f"Unknown action: {action}")

    # Check if hand is over or round is complete
    events.extend(_after_action(table))

    return events


def _do_fold(table: TableState, seat: PlayerSeat) -> list[dict]:
    seat.is_active = False
    return [_event("player_action", seat=seat.seat_index, action="fold", amount=0)]


def _do_check(table: TableState, seat: PlayerSeat) -> list[dict]:
    hand = table.hand
    assert hand is not None
    if hand.current_bet > seat.current_bet:
        raise PokerEngineError("Cannot check when there is a bet to call")
    seat.has_acted = True
    return [_event("player_action", seat=seat.seat_index, action="check", amount=0)]


def _do_call(table: TableState, seat: PlayerSeat) -> list[dict]:
    hand = table.hand
    assert hand is not None
    to_call = hand.current_bet - seat.current_bet
    if to_call <= 0:
        raise PokerEngineError("Nothing to call")
    actual = min(to_call, seat.stack)
    seat.stack -= actual
    seat.current_bet += actual
    seat.total_bet_this_hand += actual
    seat.has_acted = True
    return [_event("player_action", seat=seat.seat_index, action="call", amount=actual)]


def _do_raise(table: TableState, seat: PlayerSeat, amount: int) -> list[dict]:
    """Handle bet or raise. `amount` is additional chips to put in (on top of current_bet)."""
    hand = table.hand
    assert hand is not None

    additional = amount
    if additional <= 0:
        raise PokerEngineError("Raise amount must be positive")
    if additional > seat.stack:
        raise PokerEngineError("Insufficient stack for raise")

    new_total_bet = seat.current_bet + additional

    # Validate minimum raise
    min_raise_total = hand.current_bet + hand.min_raise
    if new_total_bet < min_raise_total and additional < seat.stack:
        raise PokerEngineError(
            f"Raise to {new_total_bet} below minimum {min_raise_total} "
            f"(unless all-in)"
        )

    raise_size = new_total_bet - hand.current_bet
    if raise_size > hand.last_raise_size:
        hand.min_raise = raise_size
    hand.last_raise_size = raise_size
    hand.current_bet = new_total_bet

    seat.stack -= additional
    seat.current_bet = new_total_bet
    seat.total_bet_this_hand += additional
    seat.has_acted = True

    # Reset has_acted for other active players (they need to respond to the raise)
    for s in table.seats:
        if s is not None and s is not seat and s.is_active and s.stack > 0:
            s.has_acted = False

    action_name = "raise" if hand.current_bet > table.big_blind or hand.phase != HandPhase.PREFLOP else "bet"
    return [_event("player_action", seat=seat.seat_index, action=action_name, amount=additional)]


def _do_all_in(table: TableState, seat: PlayerSeat) -> list[dict]:
    hand = table.hand
    assert hand is not None

    amount = seat.stack
    new_total_bet = seat.current_bet + amount

    if new_total_bet > hand.current_bet:
        raise_size = new_total_bet - hand.current_bet
        if raise_size >= hand.min_raise:
            hand.min_raise = raise_size
        hand.last_raise_size = raise_size
        hand.current_bet = new_total_bet
        # Reset has_acted for others
        for s in table.seats:
            if s is not None and s is not seat and s.is_active and s.stack > 0:
                s.has_acted = False

    seat.stack = 0
    seat.current_bet = new_total_bet
    seat.total_bet_this_hand += amount
    seat.has_acted = True

    return [_event("player_action", seat=seat.seat_index, action="all_in", amount=amount)]


# ---------------------------------------------------------------------------
# Post-action logic
# ---------------------------------------------------------------------------

def _after_action(table: TableState) -> list[dict]:
    """After a player acts, check if round/hand is over, advance state."""
    hand = table.hand
    assert hand is not None
    events: list[dict] = []

    active = hand.active_players(table.seats)

    # Only one player left — they win
    if len(active) == 1:
        events.extend(_end_hand_last_standing(table, active[0]))
        return events

    # Check if betting round is complete
    if _is_betting_round_complete(table):
        events.extend(_advance_phase(table))
    else:
        # Move to next player
        next_seat = table.next_active_seat(hand.action_on)
        if next_seat is not None and next_seat != hand.action_on:
            hand.action_on = next_seat
            _skip_all_in_players(table)
            if hand.action_on is not None:
                timeout_at = time.time() + table.action_timeout_sec
                events.append(_event("action_on", seat=hand.action_on, timeout_at=timeout_at))
        else:
            # No one else can act
            events.extend(_advance_phase(table))

    return events


def _is_betting_round_complete(table: TableState) -> bool:
    """Check if all active players with chips have acted and bets are equal."""
    hand = table.hand
    assert hand is not None

    active_with_chips = [
        s for s in table.seats
        if s is not None and s.is_active and not s.is_sitting_out and s.stack > 0
    ]

    if not active_with_chips:
        # Everyone is all-in
        return True

    # All must have acted and bet the same amount (or be all-in)
    for s in active_with_chips:
        if not s.has_acted:
            return False
        if s.current_bet < hand.current_bet:
            return False

    return True


def _advance_phase(table: TableState) -> list[dict]:
    """Advance to next betting phase or showdown."""
    hand = table.hand
    assert hand is not None
    events: list[dict] = []

    # Collect bets into pots
    _collect_bets_into_pots(table)

    active = hand.active_players(table.seats)
    can_act = hand.players_who_can_act(table.seats)

    # If only 0 or 1 player can still act, run out remaining community cards
    if len(can_act) <= 1:
        events.extend(_run_out_board(table))
        events.extend(_showdown(table))
        return events

    # Reset for next round
    for s in table.seats:
        if s is not None:
            s.current_bet = 0
            s.has_acted = False
    hand.current_bet = 0
    hand.min_raise = table.big_blind
    hand.last_raise_size = 0

    if hand.phase == HandPhase.PREFLOP:
        hand.phase = HandPhase.FLOP
        community = deal(hand.deck, 3)
        hand.community_cards.extend(community)
        events.append(_event("phase_change", phase="flop",
                             community_cards=[c.to_dict() for c in hand.community_cards]))
    elif hand.phase == HandPhase.FLOP:
        hand.phase = HandPhase.TURN
        community = deal(hand.deck, 1)
        hand.community_cards.extend(community)
        events.append(_event("phase_change", phase="turn",
                             community_cards=[c.to_dict() for c in hand.community_cards]))
    elif hand.phase == HandPhase.TURN:
        hand.phase = HandPhase.RIVER
        community = deal(hand.deck, 1)
        hand.community_cards.extend(community)
        events.append(_event("phase_change", phase="river",
                             community_cards=[c.to_dict() for c in hand.community_cards]))
    elif hand.phase == HandPhase.RIVER:
        events.extend(_showdown(table))
        return events

    # Set action: first active player after dealer
    active_count = len(hand.active_players(table.seats))
    if active_count == 2 and len(table.seated_players()) == 2:
        # Heads-up post-flop: non-dealer acts first
        hand.action_on = table.next_active_seat(hand.dealer_seat)
    else:
        hand.action_on = table.next_active_seat(hand.dealer_seat)

    _skip_all_in_players(table)

    if hand.action_on is not None:
        timeout_at = time.time() + table.action_timeout_sec
        events.append(_event("action_on", seat=hand.action_on, timeout_at=timeout_at))
    else:
        # Everyone all-in, run out board
        events.extend(_run_out_board(table))
        events.extend(_showdown(table))

    return events


def _run_out_board(table: TableState) -> list[dict]:
    """Deal remaining community cards when no more betting is possible."""
    hand = table.hand
    assert hand is not None
    events: list[dict] = []

    while len(hand.community_cards) < 5:
        cards_needed = {0: 3, 3: 1, 4: 1}.get(len(hand.community_cards), 0)
        if cards_needed == 0:
            break
        community = deal(hand.deck, cards_needed)
        hand.community_cards.extend(community)
        phase_name = {3: "flop", 4: "turn", 5: "river"}[len(hand.community_cards)]
        hand.phase = HandPhase(phase_name)
        events.append(_event("phase_change", phase=phase_name,
                             community_cards=[c.to_dict() for c in hand.community_cards]))

    return events


# ---------------------------------------------------------------------------
# Pot management
# ---------------------------------------------------------------------------

def _collect_bets_into_pots(table: TableState) -> None:
    """Collect current bets into main pot and side pots."""
    hand = table.hand
    assert hand is not None

    # Gather all bets from this round
    bettors = [(s.total_bet_this_hand, s) for s in table.seats
               if s is not None and s.total_bet_this_hand > 0]

    if not bettors:
        return

    # Rebuild pots from scratch using total_bet_this_hand
    bettors.sort(key=lambda x: x[0])

    active_players = [s for s in table.seats if s is not None and s.is_active]

    # Simple approach: sum all bets into a single main pot for now,
    # handle side pots only when there are all-in players with different bet sizes
    all_in_amounts = sorted(set(
        s.total_bet_this_hand for s in table.seats
        if s is not None and s.is_active and s.stack == 0 and s.total_bet_this_hand > 0
    ))

    if not all_in_amounts:
        # No all-ins, just one pot
        total = sum(s.total_bet_this_hand for s in table.seats if s is not None)
        hand.pots = [Pot(
            amount=total,
            eligible_players=[s.player_id for s in active_players],
        )]
        return

    # Build side pots for each all-in level.
    # Include all players who bet (even folded ones contribute money to the pot),
    # but only active players are eligible to win.
    pots: list[Pot] = []
    prev_level = 0
    all_bettors = [s for s in table.seats if s is not None and s.total_bet_this_hand > 0]

    # Build levels: each all-in amount plus the max bet (which covers non-all-in players)
    max_bet = max(s.total_bet_this_hand for s in all_bettors)
    all_levels = sorted(set(all_in_amounts + [max_bet]))

    for level in all_levels:
        pot_amount = 0
        eligible = []
        for s in all_bettors:
            contribution = min(s.total_bet_this_hand, level) - prev_level
            if contribution > 0:
                pot_amount += contribution
            # Only active (non-folded) players who bet at least this level are eligible
            if s.is_active and s.total_bet_this_hand >= level:
                eligible.append(s.player_id)

        if pot_amount > 0:
            pots.append(Pot(amount=pot_amount, eligible_players=eligible))
        prev_level = level

    hand.pots = pots if pots else [Pot(amount=0, eligible_players=[])]


# ---------------------------------------------------------------------------
# Showdown
# ---------------------------------------------------------------------------

def _showdown(table: TableState) -> list[dict]:
    """Evaluate hands and distribute pots."""
    hand = table.hand
    assert hand is not None
    hand.phase = HandPhase.SHOWDOWN
    events: list[dict] = []

    # Final pot collection
    _collect_bets_into_pots(table)

    active = hand.active_players(table.seats)

    # Evaluate each active player's hand
    player_scores: dict[str, tuple[int, str, list[Card]]] = {}
    for seat in active:
        all_cards = seat.hole_cards + hand.community_cards
        if len(all_cards) >= 5:
            score, hand_name = evaluate_hand(all_cards)
            best_cards = best_hand_cards(all_cards)
            player_scores[seat.player_id] = (score, hand_name, best_cards)

    # Distribute each pot
    showdown_results: list[dict] = []
    for pot in hand.pots:
        if pot.amount == 0:
            continue

        eligible_scores = {
            pid: player_scores[pid]
            for pid in pot.eligible_players
            if pid in player_scores
        }

        if not eligible_scores:
            continue

        # Find winner(s)
        max_score = max(s[0] for s in eligible_scores.values())
        winners = [pid for pid, s in eligible_scores.items() if s[0] == max_score]

        # Split pot equally (remainder goes to first winner by seat order)
        share = pot.amount // len(winners)
        remainder = pot.amount % len(winners)

        for i, pid in enumerate(winners):
            won = share + (1 if i == 0 else 0) * remainder
            seat = table.player_by_id(pid)
            if seat:
                seat.stack += won
                score_info = player_scores[pid]
                showdown_results.append({
                    "seat": seat.seat_index,
                    "player_id": pid,
                    "amount": won,
                    "hand_rank": score_info[1],
                    "cards_shown": [c.to_dict() for c in seat.hole_cards],
                    "best_five": [c.to_dict() for c in score_info[2]],
                })

    events.append(_event(
        "showdown",
        results=showdown_results,
        community_cards=[c.to_dict() for c in hand.community_cards],
    ))

    # Hand end event with final stacks
    stack_updates = {}
    for s in table.seats:
        if s is not None:
            stack_updates[s.player_id] = s.stack

    events.append(_event(
        "hand_end",
        hand_number=hand.hand_number,
        deck_seed_hash=hand.deck_seed_hash,
        stack_updates=stack_updates,
    ))

    hand.hand_over = True
    return events


def _end_hand_last_standing(table: TableState, winner: PlayerSeat) -> list[dict]:
    """End hand when all others have folded."""
    hand = table.hand
    assert hand is not None

    # Collect remaining bets
    _collect_bets_into_pots(table)

    # Award all pots to winner
    total_won = sum(p.amount for p in hand.pots)
    winner.stack += total_won

    events = [
        _event("hand_end",
               hand_number=hand.hand_number,
               winner_seat=winner.seat_index,
               winner_player_id=winner.player_id,
               amount=total_won,
               deck_seed_hash=hand.deck_seed_hash,
               reason="last_standing",
               stack_updates={s.player_id: s.stack for s in table.seats if s is not None}),
    ]

    hand.hand_over = True
    return events


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

def process_timeout(table: TableState, seat_idx: int) -> list[dict]:
    """Auto-fold a player who timed out."""
    hand = table.hand
    if hand is None or hand.action_on != seat_idx:
        return []

    seat = table.seats[seat_idx]
    if seat is None or not seat.is_active:
        return []

    events = [_event("player_timeout", seat=seat_idx)]
    events.extend(process_action(table, seat.player_id, PlayerAction.FOLD))
    return events
