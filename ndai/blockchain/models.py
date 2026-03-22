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


class VulnEscrowState(IntEnum):
    Created = 0
    Funded = 1
    Verified = 2
    Accepted = 3
    Rejected = 4
    Expired = 5
    PatchRefunded = 6


@dataclass
class VulnDealState:
    seller: str
    buyer: str
    operator: str
    platform: str
    price_wei: int
    deadline: int
    is_exclusive: bool
    attestation_hash: bytes
    delivery_hash: bytes
    key_commitment: bytes
    is_patched: bool
    state: VulnEscrowState
    balance_wei: int


class VerificationDepositState(IntEnum):
    Active = 0
    Refunded = 1
    Forfeited = 2


@dataclass
class DepositInfo:
    seller: str
    amount: int
    settled: bool
