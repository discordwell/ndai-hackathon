"""Session verification chain — cryptographic proof of TEE session integrity.

Builds a SHA-256 linked hash chain of all session events, producing
human-readable attestation claims and a tamper-evident final hash.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class VerificationEvent:
    """A single recorded event in the verification chain."""
    event_type: str
    timestamp: str
    data_hash: str  # SHA-256 of event data
    description: str


@dataclass
class VerificationReport:
    """Final output of the verification chain."""
    session_id: str
    events: list[dict[str, str]]
    chain_hashes: list[str]
    final_hash: str
    attestation_claims: list[str]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "events": self.events,
            "chain_hashes": self.chain_hashes,
            "final_hash": self.final_hash,
            "attestation_claims": self.attestation_claims,
        }


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# Maps event types to human-readable attestation claims
_CLAIM_TEMPLATES: dict[str, str] = {
    "session_start": "TEE session initialized with verified configuration",
    "policy_generated": "Policy was generated from context using LLM",
    "policy_enforced": "Policy was enforced deterministically (no LLM)",
    "llm_call": "LLM called {count} time(s) with egress logging",
    "sensitive_data_cleared": "Sensitive data deleted from session memory",
    "result_produced": "Result produced and validated against policy",
    # Poker-specific claims
    "hand_start": "Hand initialized with dealer rotation inside TEE",
    "deck_shuffled": "Deck shuffled with CSPRNG (hardware entropy) via Fisher-Yates",
    "hole_cards_dealt": "Hole cards dealt to players (sealed inside enclave)",
    "player_action": "Player action validated and applied deterministically",
    "community_cards": "Community cards revealed from sealed deck",
    "showdown": "Hands evaluated and winner determined deterministically",
    "hand_settled": "Chips distributed to winners, seed hash published for verification",
}


class SessionVerificationChain:
    """Builds a linked hash chain of session events."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())
        self._events: list[VerificationEvent] = []
        self._chain_hashes: list[str] = []
        self._prev_hash = "0" * 64  # genesis hash
        self._llm_call_count = 0

    def record(self, event_type: str, data: Any, description: str) -> None:
        """Record an event in the chain.

        Args:
            event_type: Category of event (e.g. 'policy_generated', 'llm_call').
            data: Arbitrary data to hash (will be JSON-serialized).
            description: Human-readable description of what happened.
        """
        data_str = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
        data_hash = _sha256(data_str)

        event = VerificationEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data_hash=data_hash,
            description=description,
        )
        self._events.append(event)

        # Linked hash: SHA-256(prev_hash + event_type + data_hash)
        chain_input = f"{self._prev_hash}{event_type}{data_hash}"
        chain_hash = _sha256(chain_input)
        self._chain_hashes.append(chain_hash)
        self._prev_hash = chain_hash

        if event_type == "llm_call":
            self._llm_call_count += 1

    def finalize(self) -> VerificationReport:
        """Finalize the chain and produce attestation claims."""
        claims: list[str] = []
        seen_types: set[str] = set()

        for event in self._events:
            if event.event_type not in seen_types:
                seen_types.add(event.event_type)
                template = _CLAIM_TEMPLATES.get(event.event_type)
                if template:
                    if "{count}" in template:
                        claims.append(template.format(count=self._llm_call_count))
                    else:
                        claims.append(template)

        return VerificationReport(
            session_id=self.session_id,
            events=[
                {
                    "event_type": e.event_type,
                    "timestamp": e.timestamp,
                    "data_hash": e.data_hash,
                    "description": e.description,
                }
                for e in self._events
            ],
            chain_hashes=list(self._chain_hashes),
            final_hash=self._prev_hash,
            attestation_claims=claims,
        )
