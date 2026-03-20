"""Tests for poker deck shuffle and deal."""

import collections

import pytest

from ndai.enclave.poker.deck import deal, make_standard_deck, shuffle_deck
from ndai.enclave.poker.state import Card, Suit


class TestMakeStandardDeck:
    def test_has_52_cards(self):
        deck = make_standard_deck()
        assert len(deck) == 52

    def test_all_unique(self):
        deck = make_standard_deck()
        assert len(set(deck)) == 52

    def test_13_per_suit(self):
        deck = make_standard_deck()
        for suit in Suit:
            cards_of_suit = [c for c in deck if c.suit == suit]
            assert len(cards_of_suit) == 13

    def test_ranks_2_to_14(self):
        deck = make_standard_deck()
        ranks = {c.rank for c in deck}
        assert ranks == set(range(2, 15))


class TestShuffle:
    def test_returns_52_unique_cards(self):
        deck, seed, seed_hash = shuffle_deck()
        assert len(deck) == 52
        assert len(set(deck)) == 52

    def test_deterministic_with_same_seed(self):
        seed = b"\x42" * 32
        deck1, _, hash1 = shuffle_deck(seed=seed)
        deck2, _, hash2 = shuffle_deck(seed=seed)
        assert deck1 == deck2
        assert hash1 == hash2

    def test_different_seeds_produce_different_orders(self):
        deck1, _, _ = shuffle_deck(seed=b"\x01" * 32)
        deck2, _, _ = shuffle_deck(seed=b"\x02" * 32)
        assert deck1 != deck2

    def test_seed_hash_is_hex_string(self):
        _, _, seed_hash = shuffle_deck()
        assert len(seed_hash) == 64  # sha256 hex
        int(seed_hash, 16)  # should not raise

    def test_shuffle_is_not_identity(self):
        """Shuffle should change order (statistically impossible to be sorted)."""
        ordered = make_standard_deck()
        shuffled, _, _ = shuffle_deck()
        assert shuffled != ordered

    def test_distribution_fairness(self):
        """Each card should appear in each position with roughly equal frequency."""
        n_trials = 5000
        position_counts: dict[int, collections.Counter] = {
            i: collections.Counter() for i in range(52)
        }
        for _ in range(n_trials):
            deck, _, _ = shuffle_deck()
            for pos, card in enumerate(deck):
                position_counts[pos][card] += 1

        # Expected: n_trials / 52 ≈ 96 per position per card
        expected = n_trials / 52
        for pos in range(52):
            for card, count in position_counts[pos].items():
                # Allow 4x deviation (very generous for statistical test)
                assert count < expected * 4, (
                    f"Card {card} appeared {count} times at position {pos}, "
                    f"expected ~{expected:.0f}"
                )


class TestDeal:
    def test_deal_removes_from_deck(self):
        deck, _, _ = shuffle_deck(seed=b"\x00" * 32)
        original_len = len(deck)
        dealt = deal(deck, 5)
        assert len(dealt) == 5
        assert len(deck) == original_len - 5

    def test_dealt_cards_come_from_top(self):
        deck, _, _ = shuffle_deck(seed=b"\x00" * 32)
        top5 = deck[:5]
        dealt = deal(deck, 5)
        assert dealt == top5

    def test_deal_all_cards(self):
        deck, _, _ = shuffle_deck()
        dealt = deal(deck, 52)
        assert len(dealt) == 52
        assert len(deck) == 0

    def test_deal_too_many_raises(self):
        deck, _, _ = shuffle_deck()
        with pytest.raises(ValueError, match="Cannot deal"):
            deal(deck, 53)

    def test_deal_zero(self):
        deck, _, _ = shuffle_deck()
        dealt = deal(deck, 0)
        assert dealt == []
        assert len(deck) == 52


class TestCard:
    def test_repr(self):
        c = Card(rank=14, suit=Suit.SPADES)
        assert "A" in repr(c)

    def test_to_dict_roundtrip(self):
        c = Card(rank=10, suit=Suit.HEARTS)
        d = c.to_dict()
        assert Card.from_dict(d) == c

    def test_frozen(self):
        c = Card(rank=5, suit=Suit.CLUBS)
        with pytest.raises(AttributeError):
            c.rank = 6  # type: ignore

    def test_hashable(self):
        c1 = Card(rank=5, suit=Suit.CLUBS)
        c2 = Card(rank=5, suit=Suit.CLUBS)
        assert hash(c1) == hash(c2)
        assert {c1, c2} == {c1}
