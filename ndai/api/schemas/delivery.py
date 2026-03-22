"""Sealed delivery request/response schemas."""

from pydantic import BaseModel


class BuyerKeySubmitRequest(BaseModel):
    """Buyer submits their public key encrypted to the enclave."""
    encrypted_public_key: str  # base64-encoded ECIES(enclave_pub, buyer_pub_der)


class DeliveryStatusResponse(BaseModel):
    delivery_hash: str
    key_commitment: str
    status: str  # "sealed" | "released"


class DeliveryVerifyResponse(BaseModel):
    delivery_hash_matches: bool
    key_commitment_matches: bool
    on_chain_verified: bool
