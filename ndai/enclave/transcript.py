"""Hash-chain for negotiation transcripts.

Each message is hashed with the previous hash to form a tamper-evident chain.
"""

import hashlib
import json
from typing import Any

GENESIS_HASH = b"\x00" * 32


def hash_message(msg: dict[str, Any], prev_hash: bytes) -> bytes:
    """Hash a message with the previous hash in the chain.

    Args:
        msg: Message dict to hash.
        prev_hash: Previous 32-byte hash in the chain.

    Returns:
        SHA-256 hash of (prev_hash + canonical_json(msg)).
    """
    canonical = json.dumps(msg, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(prev_hash + canonical).digest()


def build_transcript_chain(messages: list[dict[str, Any]]) -> list[bytes]:
    """Build a hash chain from a list of messages.

    Returns:
        List of hashes, one per message. The first is hash(GENESIS + msg[0]).
    """
    chain: list[bytes] = []
    prev = GENESIS_HASH
    for msg in messages:
        h = hash_message(msg, prev)
        chain.append(h)
        prev = h
    return chain


def verify_transcript_chain(
    messages: list[dict[str, Any]], chain: list[bytes]
) -> bool:
    """Verify that a hash chain is consistent with the messages.

    Returns:
        True if every hash matches, False if tampered.
    """
    if len(messages) != len(chain):
        return False
    expected = build_transcript_chain(messages)
    return all(a == b for a, b in zip(expected, chain))
