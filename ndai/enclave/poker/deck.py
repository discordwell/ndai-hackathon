"""Cryptographically fair deck shuffle and deal.

Uses os.urandom for the seed (hardware entropy in Nitro Enclave via /dev/urandom).
Fisher-Yates shuffle with SHA-256 based deterministic PRNG from the seed.
The seed and deck state never leave the enclave.
"""

from __future__ import annotations

import hashlib
import os
import struct

from ndai.enclave.poker.state import Card, Suit


def make_standard_deck() -> list[Card]:
    """Create an ordered 52-card deck."""
    return [Card(rank=r, suit=s) for s in Suit for r in range(2, 15)]


def shuffle_deck(seed: bytes | None = None) -> tuple[list[Card], bytes, str]:
    """Shuffle a deck using CSPRNG.

    Returns (shuffled_deck, seed, seed_hash).
    The seed_hash can be published for post-hoc verification.
    The seed itself must stay inside the enclave during play.
    """
    if seed is None:
        seed = os.urandom(32)

    seed_hash = hashlib.sha256(seed).hexdigest()
    deck = make_standard_deck()
    _fisher_yates(deck, seed)
    return deck, seed, seed_hash


def _fisher_yates(deck: list[Card], seed: bytes) -> None:
    """Fisher-Yates shuffle using deterministic PRNG derived from seed."""
    prng = _DeterministicPRNG(seed)
    n = len(deck)
    for i in range(n - 1, 0, -1):
        j = prng.randbelow(i + 1)
        deck[i], deck[j] = deck[j], deck[i]


class _DeterministicPRNG:
    """SHA-256 counter-mode PRNG for deterministic shuffle.

    Produces uniformly distributed random integers using rejection sampling
    to avoid modulo bias.
    """

    def __init__(self, seed: bytes) -> None:
        self._seed = seed
        self._counter = 0
        self._buffer = b""
        self._pos = 0

    def _next_bytes(self, n: int) -> bytes:
        result = bytearray()
        while len(result) < n:
            if self._pos >= len(self._buffer):
                self._buffer = hashlib.sha256(
                    self._seed + struct.pack(">Q", self._counter)
                ).digest()
                self._counter += 1
                self._pos = 0
            chunk = self._buffer[self._pos : self._pos + (n - len(result))]
            result.extend(chunk)
            self._pos += len(chunk)
        return bytes(result)

    def randbelow(self, upper: int) -> int:
        """Return uniform random int in [0, upper). Rejection sampling to avoid bias."""
        if upper <= 0:
            raise ValueError("upper must be positive")
        if upper == 1:
            return 0
        # Find smallest k such that 2^(8*k) >= upper
        k = (upper - 1).bit_length()
        byte_count = (k + 7) // 8
        mask = (1 << k) - 1
        while True:
            raw = int.from_bytes(self._next_bytes(byte_count), "big") & mask
            if raw < upper:
                return raw


def deal(deck: list[Card], n: int) -> list[Card]:
    """Deal n cards from the top of the deck (mutates deck)."""
    if n > len(deck):
        raise ValueError(f"Cannot deal {n} cards from deck of {len(deck)}")
    dealt = deck[:n]
    del deck[:n]
    return dealt
