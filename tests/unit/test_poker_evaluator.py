"""Tests for poker hand evaluator."""

import pytest

from ndai.enclave.poker.evaluator import (
    FLUSH,
    FOUR_OF_A_KIND,
    FULL_HOUSE,
    HIGH_CARD,
    ONE_PAIR,
    ROYAL_FLUSH,
    STRAIGHT,
    STRAIGHT_FLUSH,
    THREE_OF_A_KIND,
    TWO_PAIR,
    best_hand_cards,
    compare_hands,
    evaluate_hand,
)
from ndai.enclave.poker.state import Card, Suit

S, H, D, C = Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS


def _cards(*specs: tuple[int, Suit]) -> list[Card]:
    return [Card(rank=r, suit=s) for r, s in specs]


class TestHandRanking:
    def test_royal_flush(self):
        cards = _cards((14, S), (13, S), (12, S), (11, S), (10, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == ROYAL_FLUSH
        assert name == "Royal Flush"

    def test_straight_flush(self):
        cards = _cards((9, H), (8, H), (7, H), (6, H), (5, H))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == STRAIGHT_FLUSH
        assert name == "Straight Flush"

    def test_four_of_a_kind(self):
        cards = _cards((8, S), (8, H), (8, D), (8, C), (3, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == FOUR_OF_A_KIND
        assert name == "Four of a Kind"

    def test_full_house(self):
        cards = _cards((10, S), (10, H), (10, D), (4, C), (4, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == FULL_HOUSE
        assert name == "Full House"

    def test_flush(self):
        cards = _cards((14, D), (10, D), (7, D), (5, D), (2, D))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == FLUSH
        assert name == "Flush"

    def test_straight(self):
        cards = _cards((9, S), (8, H), (7, D), (6, C), (5, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == STRAIGHT
        assert name == "Straight"

    def test_wheel_straight(self):
        """A-2-3-4-5 is the lowest straight."""
        cards = _cards((14, S), (2, H), (3, D), (4, C), (5, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == STRAIGHT
        assert name == "Straight"

    def test_three_of_a_kind(self):
        cards = _cards((7, S), (7, H), (7, D), (10, C), (2, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == THREE_OF_A_KIND
        assert name == "Three of a Kind"

    def test_two_pair(self):
        cards = _cards((11, S), (11, H), (5, D), (5, C), (2, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == TWO_PAIR
        assert name == "Two Pair"

    def test_one_pair(self):
        cards = _cards((9, S), (9, H), (14, D), (7, C), (3, S))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == ONE_PAIR
        assert name == "One Pair"

    def test_high_card(self):
        cards = _cards((14, S), (10, H), (7, D), (5, C), (2, H))
        score, name = evaluate_hand(cards)
        assert (score >> 24) == HIGH_CARD
        assert name == "High Card"


class TestHandComparison:
    def test_flush_beats_straight(self):
        flush = _cards((14, D), (10, D), (7, D), (5, D), (2, D))
        straight = _cards((9, S), (8, H), (7, D), (6, C), (5, S))
        assert compare_hands(flush, straight) > 0

    def test_pair_aces_beats_pair_kings(self):
        pair_a = _cards((14, S), (14, H), (10, D), (7, C), (3, S))
        pair_k = _cards((13, S), (13, H), (10, D), (7, C), (3, H))
        assert compare_hands(pair_a, pair_k) > 0

    def test_higher_kicker_wins(self):
        hand_a = _cards((14, S), (14, H), (13, D), (7, C), (3, S))
        hand_b = _cards((14, D), (14, C), (12, D), (7, H), (3, H))
        assert compare_hands(hand_a, hand_b) > 0

    def test_identical_hands_tie(self):
        hand_a = _cards((14, S), (13, H), (10, D), (7, C), (3, S))
        hand_b = _cards((14, H), (13, D), (10, C), (7, S), (3, D))
        assert compare_hands(hand_a, hand_b) == 0

    def test_wheel_loses_to_six_high_straight(self):
        wheel = _cards((14, S), (2, H), (3, D), (4, C), (5, S))
        six_high = _cards((6, S), (5, H), (4, D), (3, C), (2, S))
        assert compare_hands(six_high, wheel) > 0

    def test_full_house_trips_matter(self):
        """Full house: higher trips wins regardless of pair."""
        fh_high = _cards((10, S), (10, H), (10, D), (2, C), (2, S))
        fh_low = _cards((9, S), (9, H), (9, D), (14, C), (14, S))
        assert compare_hands(fh_high, fh_low) > 0


class TestSevenCardEvaluation:
    def test_best_five_from_seven(self):
        """Should find the flush in 7 cards even with distracting pairs."""
        cards = _cards(
            (14, D), (10, D), (7, D), (5, D), (2, D),  # flush
            (10, S), (7, H),  # distractors
        )
        score, name = evaluate_hand(cards)
        assert name == "Flush"

    def test_full_house_from_seven(self):
        cards = _cards(
            (10, S), (10, H), (10, D),  # trips
            (5, C), (5, S),             # pair
            (14, H), (2, D),            # distractors
        )
        score, name = evaluate_hand(cards)
        assert name == "Full House"

    def test_straight_from_seven(self):
        cards = _cards(
            (9, S), (8, H), (7, D), (6, C), (5, S),
            (2, H), (2, D),  # pair (but straight is better)
        )
        score, name = evaluate_hand(cards)
        assert name == "Straight"

    def test_two_pair_kicker(self):
        """With 7 cards, the best kicker should be selected."""
        cards = _cards(
            (11, S), (11, H), (5, D), (5, C),
            (14, S),  # best kicker
            (3, H), (2, D),
        )
        score, _ = evaluate_hand(cards)
        # Compare with version where best kicker is lower
        cards2 = _cards(
            (11, D), (11, C), (5, H), (5, S),
            (13, S),  # slightly worse kicker
            (3, D), (2, H),
        )
        score2, _ = evaluate_hand(cards2)
        assert score > score2


class TestBestHandCards:
    def test_returns_five_cards(self):
        cards = _cards(
            (14, S), (13, H), (12, D), (11, C), (10, S),
            (5, H), (2, D),
        )
        best = best_hand_cards(cards)
        assert len(best) == 5

    def test_fewer_than_five(self):
        cards = _cards((14, S), (10, H), (7, D))
        best = best_hand_cards(cards)
        assert len(best) == 3


class TestEdgeCases:
    def test_fewer_than_five_raises(self):
        cards = _cards((14, S), (10, H), (7, D), (5, C))
        with pytest.raises(ValueError, match="at least 5"):
            evaluate_hand(cards)

    def test_broadway_straight(self):
        cards = _cards((14, S), (13, H), (12, D), (11, C), (10, S))
        score, name = evaluate_hand(cards)
        assert name == "Straight"

    def test_ace_high_flush_beats_king_high_flush(self):
        ace_flush = _cards((14, H), (10, H), (7, H), (5, H), (2, H))
        king_flush = _cards((13, H), (10, H), (7, H), (5, H), (2, H))
        # Need different suits to avoid duplicate cards
        king_flush = _cards((13, D), (10, D), (7, D), (5, D), (2, D))
        assert compare_hands(ace_flush, king_flush) > 0
