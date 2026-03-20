"""Blockchain data models."""
from dataclasses import dataclass
from enum import IntEnum


class EscrowState(IntEnum):
    Created = 0
    Funded = 1
    Evaluated = 2
    Accepted = 3
    Rejected = 4
    Expired = 5


@dataclass
class DealState:
    seller: str
    buyer: str
    operator: str
    reserve_price_wei: int
    budget_cap_wei: int
    final_price_wei: int
    attestation_hash: bytes
    deadline: int
    state: EscrowState
    balance_wei: int
