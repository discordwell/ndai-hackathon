"""Poker hand evaluator.

Evaluates the best 5-card hand from 7 cards (2 hole + 5 community).
Each hand maps to a comparable integer: higher = better.

Hand ranking encoding (32-bit integer):
    Bits 24-27: Hand category (0=high card .. 9=straight flush)
    Bits 0-23:  Tiebreaker ranks (up to 5 nibbles of 4 bits each,
                packed high to low)

This allows simple integer comparison for hand ranking.
"""

from __future__ import annotations

from itertools import combinations

from ndai.enclave.poker.state import Card

# Hand category constants
HIGH_CARD = 0
ONE_PAIR = 1
TWO_PAIR = 2
THREE_OF_A_KIND = 3
STRAIGHT = 4
FLUSH = 5
FULL_HOUSE = 6
FOUR_OF_A_KIND = 7
STRAIGHT_FLUSH = 8
ROYAL_FLUSH = 9  # scored same as straight flush (Ace-high)

HAND_NAMES = {
    HIGH_CARD: "High Card",
    ONE_PAIR: "One Pair",
    TWO_PAIR: "Two Pair",
    THREE_OF_A_KIND: "Three of a Kind",
    STRAIGHT: "Straight",
    FLUSH: "Flush",
    FULL_HOUSE: "Full House",
    FOUR_OF_A_KIND: "Four of a Kind",
    STRAIGHT_FLUSH: "Straight Flush",
    ROYAL_FLUSH: "Royal Flush",
}


def _pack_score(category: int, tiebreakers: list[int]) -> int:
    """Pack hand category and tiebreaker ranks into a single comparable int."""
    score = category << 24
    for i, tb in enumerate(tiebreakers[:5]):
        score |= tb << (4 * (4 - i))
    return score


def _evaluate_5(cards: list[Card]) -> int:
    """Score a 5-card hand. Returns a comparable integer (higher = better)."""
    ranks = sorted([c.rank for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    is_flush = len(set(suits)) == 1

    # Check for straight (including A-2-3-4-5 wheel)
    is_straight = False
    straight_high = 0
    if ranks[0] - ranks[4] == 4 and len(set(ranks)) == 5:
        is_straight = True
        straight_high = ranks[0]
    elif ranks == [14, 5, 4, 3, 2]:  # Ace-low straight (wheel)
        is_straight = True
        straight_high = 5  # 5-high straight

    # Count rank frequencies
    freq: dict[int, int] = {}
    for r in ranks:
        freq[r] = freq.get(r, 0) + 1

    # Sort groups: by count desc, then by rank desc
    groups = sorted(freq.items(), key=lambda x: (x[1], x[0]), reverse=True)
    counts = [g[1] for g in groups]
    group_ranks = [g[0] for g in groups]

    if is_straight and is_flush:
        cat = ROYAL_FLUSH if straight_high == 14 else STRAIGHT_FLUSH
        return _pack_score(cat, [straight_high])

    if counts == [4, 1]:
        return _pack_score(FOUR_OF_A_KIND, group_ranks)

    if counts == [3, 2]:
        return _pack_score(FULL_HOUSE, group_ranks)

    if is_flush:
        return _pack_score(FLUSH, ranks)

    if is_straight:
        return _pack_score(STRAIGHT, [straight_high])

    if counts == [3, 1, 1]:
        return _pack_score(THREE_OF_A_KIND, group_ranks)

    if counts == [2, 2, 1]:
        return _pack_score(TWO_PAIR, group_ranks)

    if counts == [2, 1, 1, 1]:
        return _pack_score(ONE_PAIR, group_ranks)

    return _pack_score(HIGH_CARD, ranks)


def evaluate_hand(cards: list[Card]) -> tuple[int, str]:
    """Evaluate the best 5-card hand from a list of cards (typically 7).

    Returns (score, hand_name) where score is a comparable integer.
    """
    if len(cards) < 5:
        raise ValueError(f"Need at least 5 cards, got {len(cards)}")

    best_score = -1
    for combo in combinations(cards, 5):
        score = _evaluate_5(list(combo))
        if score > best_score:
            best_score = score

    category = (best_score >> 24) & 0xF
    return best_score, HAND_NAMES.get(category, "Unknown")


def best_hand_cards(cards: list[Card]) -> list[Card]:
    """Return the best 5-card combination from the given cards."""
    if len(cards) < 5:
        return list(cards)

    best_score = -1
    best_combo: list[Card] = []
    for combo in combinations(cards, 5):
        score = _evaluate_5(list(combo))
        if score > best_score:
            best_score = score
            best_combo = list(combo)

    return sorted(best_combo, key=lambda c: c.rank, reverse=True)


def compare_hands(hand_a: list[Card], hand_b: list[Card]) -> int:
    """Compare two hands. Returns positive if a wins, negative if b wins, 0 if tie."""
    score_a, _ = evaluate_hand(hand_a)
    score_b, _ = evaluate_hand(hand_b)
    return score_a - score_b
