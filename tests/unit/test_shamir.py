"""Tests for Shamir's Secret Sharing implementation."""

import secrets

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ndai.crypto.shamir import PRIME, Share, reconstruct, reconstruct_bytes, split


class TestSplit:
    def test_basic_split(self):
        secret = 42
        shares = split(secret, k=3, n=5)
        assert len(shares) == 5
        assert all(isinstance(s, Share) for s in shares)
        assert all(1 <= s.index <= 5 for s in shares)

    def test_split_bytes(self):
        secret_bytes = secrets.token_bytes(32)
        shares = split(secret_bytes, k=3, n=5)
        assert len(shares) == 5

    def test_split_invalid_threshold(self):
        with pytest.raises(ValueError, match="Threshold k must be >= 2"):
            split(42, k=1, n=5)

    def test_split_n_less_than_k(self):
        with pytest.raises(ValueError, match="must be >= threshold"):
            split(42, k=5, n=3)

    def test_split_secret_out_of_range(self):
        with pytest.raises(ValueError, match="must be in range"):
            split(PRIME, k=3, n=5)

    def test_split_negative_secret(self):
        with pytest.raises(ValueError, match="must be in range"):
            split(-1, k=3, n=5)

    def test_unique_share_indices(self):
        shares = split(100, k=3, n=10)
        indices = [s.index for s in shares]
        assert len(set(indices)) == 10


class TestReconstruct:
    def test_basic_reconstruct(self):
        secret = 12345
        shares = split(secret, k=3, n=5)
        recovered = reconstruct(shares[:3])
        assert recovered == secret

    def test_reconstruct_with_all_shares(self):
        secret = 99999
        shares = split(secret, k=3, n=5)
        recovered = reconstruct(shares)
        assert recovered == secret

    def test_reconstruct_different_subsets(self):
        secret = 54321
        shares = split(secret, k=3, n=5)
        # Any 3-of-5 subset should work
        for i in range(5):
            for j in range(i + 1, 5):
                for m in range(j + 1, 5):
                    subset = [shares[i], shares[j], shares[m]]
                    assert reconstruct(subset) == secret

    def test_reconstruct_bytes_roundtrip(self):
        secret_bytes = secrets.token_bytes(32)
        shares = split(secret_bytes, k=3, n=5)
        recovered = reconstruct_bytes(shares[:3], length=32)
        assert recovered == secret_bytes

    def test_insufficient_shares_gives_wrong_result(self):
        secret = 42
        shares = split(secret, k=3, n=5)
        # With only 2 shares (below threshold of 3), result should be wrong
        wrong = reconstruct(shares[:2])
        # It's theoretically possible but astronomically unlikely to get the right answer
        assert wrong != secret

    def test_reconstruct_too_few_shares(self):
        with pytest.raises(ValueError, match="at least 2"):
            reconstruct([Share(1, 100)])

    def test_reconstruct_duplicate_indices(self):
        with pytest.raises(ValueError, match="Duplicate"):
            reconstruct([Share(1, 100), Share(1, 200), Share(2, 300)])

    def test_zero_secret(self):
        shares = split(0, k=3, n=5)
        assert reconstruct(shares[:3]) == 0

    def test_max_secret(self):
        secret = PRIME - 1
        shares = split(secret, k=3, n=5)
        assert reconstruct(shares[:3]) == secret


class TestPropertyBased:
    @given(
        secret=st.integers(min_value=0, max_value=PRIME - 1),
        k=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=50)
    def test_split_reconstruct_roundtrip(self, secret, k):
        n = k + 2
        shares = split(secret, k=k, n=n)
        recovered = reconstruct(shares[:k])
        assert recovered == secret

    @given(data=st.data())
    @settings(max_examples=30)
    def test_any_k_subset_works(self, data):
        secret = data.draw(st.integers(min_value=0, max_value=10**18))
        k = data.draw(st.integers(min_value=2, max_value=5))
        n = data.draw(st.integers(min_value=k, max_value=k + 3))
        shares = split(secret, k=k, n=n)

        # Draw a random subset of size k
        indices = data.draw(
            st.lists(
                st.sampled_from(list(range(n))),
                min_size=k,
                max_size=k,
                unique=True,
            )
        )
        subset = [shares[i] for i in indices]
        assert reconstruct(subset) == secret
