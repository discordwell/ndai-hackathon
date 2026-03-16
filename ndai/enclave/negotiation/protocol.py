"""Negotiation protocol state machine.

Manages the multi-round negotiation between seller and buyer agents,
enforcing the NDAI protocol structure and constraints.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class MessageType(Enum):
    DISCLOSURE = "disclosure"
    EVALUATION = "evaluation"
    OFFER = "offer"
    COUNTEROFFER = "counteroffer"
    ACCEPT = "accept"
    REJECT = "reject"
    FINAL_DECISION = "final_decision"


class SessionState(Enum):
    INITIALIZED = "initialized"
    AWAITING_DISCLOSURE = "awaiting_disclosure"
    DISCLOSURE_MADE = "disclosure_made"
    NEGOTIATING = "negotiating"
    RESOLVED_AGREEMENT = "resolved_agreement"
    RESOLVED_NO_DEAL = "resolved_no_deal"
    ERROR = "error"


@dataclass
class NegotiationMessage:
    """A single message in the negotiation protocol."""

    msg_type: MessageType
    sender: str  # "seller_agent", "buyer_agent", or "system"
    round_number: int
    content: dict[str, Any]  # Structured payload (disclosure, offer, etc.)
    explanation: str = ""  # Visible to the other agent
    private_reasoning: str = ""  # Not shared
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class ProtocolState:
    """Current state of a negotiation session."""

    session_id: str
    state: SessionState = SessionState.INITIALIZED
    current_round: int = 0
    max_rounds: int = 5
    messages: list[NegotiationMessage] = field(default_factory=list)
    disclosed_value: float | None = None
    current_offer: float | None = None
    final_price: float | None = None
    error: str | None = None

    def is_terminal(self) -> bool:
        return self.state in (
            SessionState.RESOLVED_AGREEMENT,
            SessionState.RESOLVED_NO_DEAL,
            SessionState.ERROR,
        )


def create_session(session_id: str | None = None, max_rounds: int = 5) -> ProtocolState:
    """Create a new negotiation session."""
    return ProtocolState(
        session_id=session_id or str(uuid4()),
        state=SessionState.AWAITING_DISCLOSURE,
        max_rounds=max_rounds,
    )


def apply_disclosure(
    state: ProtocolState, omega_hat: float, explanation: str = ""
) -> ProtocolState:
    """Record the seller's disclosure."""
    if state.state != SessionState.AWAITING_DISCLOSURE:
        state.error = f"Cannot disclose in state {state.state.value}"
        state.state = SessionState.ERROR
        return state

    msg = NegotiationMessage(
        msg_type=MessageType.DISCLOSURE,
        sender="seller_agent",
        round_number=0,
        content={"omega_hat": omega_hat},
        explanation=explanation,
    )
    state.messages.append(msg)
    state.disclosed_value = omega_hat
    state.state = SessionState.DISCLOSURE_MADE
    return state


def apply_offer(
    state: ProtocolState,
    sender: str,
    price: float,
    explanation: str = "",
) -> ProtocolState:
    """Record a price offer or counteroffer."""
    if state.state not in (SessionState.DISCLOSURE_MADE, SessionState.NEGOTIATING):
        state.error = f"Cannot offer in state {state.state.value}"
        state.state = SessionState.ERROR
        return state

    msg_type = MessageType.OFFER if sender == "buyer_agent" else MessageType.COUNTEROFFER
    state.current_round += 1
    msg = NegotiationMessage(
        msg_type=msg_type,
        sender=sender,
        round_number=state.current_round,
        content={"price": price},
        explanation=explanation,
    )
    state.messages.append(msg)
    state.current_offer = price
    state.state = SessionState.NEGOTIATING
    return state


def apply_resolution(
    state: ProtocolState,
    agreed: bool,
    final_price: float | None = None,
    reason: str = "",
) -> ProtocolState:
    """Record the final resolution."""
    msg = NegotiationMessage(
        msg_type=MessageType.FINAL_DECISION,
        sender="system",
        round_number=state.current_round,
        content={"agreed": agreed, "final_price": final_price, "reason": reason},
    )
    state.messages.append(msg)

    if agreed and final_price is not None:
        state.final_price = final_price
        state.state = SessionState.RESOLVED_AGREEMENT
    else:
        state.state = SessionState.RESOLVED_NO_DEAL

    return state


def has_rounds_remaining(state: ProtocolState) -> bool:
    """Check if there are negotiation rounds left."""
    return state.current_round < state.max_rounds
