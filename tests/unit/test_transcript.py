"""Tests for transcript hash chain integrity."""

import pytest

from ndai.enclave.transcript import (
    GENESIS_HASH,
    build_transcript_chain,
    hash_message,
    verify_transcript_chain,
)


class TestHashChain:
    def test_genesis_hash_is_32_zero_bytes(self):
        assert len(GENESIS_HASH) == 32
        assert GENESIS_HASH == b"\x00" * 32

    def test_hash_message_returns_32_bytes(self):
        h = hash_message({"role": "seller", "content": "hello"}, GENESIS_HASH)
        assert len(h) == 32
        assert isinstance(h, bytes)

    def test_hash_is_deterministic(self):
        msg = {"role": "buyer", "value": 0.5}
        h1 = hash_message(msg, GENESIS_HASH)
        h2 = hash_message(msg, GENESIS_HASH)
        assert h1 == h2

    def test_hash_changes_with_different_prev(self):
        msg = {"role": "seller"}
        h1 = hash_message(msg, GENESIS_HASH)
        h2 = hash_message(msg, b"\x01" * 32)
        assert h1 != h2

    def test_build_chain_empty(self):
        chain = build_transcript_chain([])
        assert chain == []

    def test_build_chain_single_message(self):
        msgs = [{"role": "seller", "action": "disclose"}]
        chain = build_transcript_chain(msgs)
        assert len(chain) == 1
        assert chain[0] == hash_message(msgs[0], GENESIS_HASH)

    def test_build_chain_links_correctly(self):
        msgs = [
            {"role": "seller", "action": "disclose", "value": 0.7},
            {"role": "buyer", "action": "evaluate", "value": 0.65},
            {"role": "system", "action": "resolve", "price": 0.4},
        ]
        chain = build_transcript_chain(msgs)
        assert len(chain) == 3

        # Verify manual chain construction
        expected_0 = hash_message(msgs[0], GENESIS_HASH)
        expected_1 = hash_message(msgs[1], expected_0)
        expected_2 = hash_message(msgs[2], expected_1)
        assert chain[0] == expected_0
        assert chain[1] == expected_1
        assert chain[2] == expected_2

    def test_verify_valid_chain(self):
        msgs = [
            {"role": "seller", "value": 0.7},
            {"role": "buyer", "value": 0.65},
        ]
        chain = build_transcript_chain(msgs)
        assert verify_transcript_chain(msgs, chain) is True

    def test_verify_tampered_message(self):
        msgs = [
            {"role": "seller", "value": 0.7},
            {"role": "buyer", "value": 0.65},
        ]
        chain = build_transcript_chain(msgs)

        # Tamper with a message
        tampered = [
            {"role": "seller", "value": 0.9},  # changed 0.7 -> 0.9
            {"role": "buyer", "value": 0.65},
        ]
        assert verify_transcript_chain(tampered, chain) is False

    def test_verify_wrong_length(self):
        msgs = [{"role": "seller"}]
        chain = build_transcript_chain(msgs)
        assert verify_transcript_chain([], chain) is False
        assert verify_transcript_chain(msgs + [{"extra": True}], chain) is False

    def test_key_ordering_canonical(self):
        """JSON canonicalization: key order shouldn't matter."""
        msg_a = {"z": 1, "a": 2}
        msg_b = {"a": 2, "z": 1}
        assert hash_message(msg_a, GENESIS_HASH) == hash_message(msg_b, GENESIS_HASH)
