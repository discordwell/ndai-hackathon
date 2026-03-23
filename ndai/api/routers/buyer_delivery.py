"""Buyer delivery endpoints — request sealed exploit delivery for verified listings."""

import base64
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_zk_identity
from ndai.db.session import get_db
from ndai.models.zk_vulnerability import ZKVulnerability, ZKVulnAgreement

router = APIRouter(prefix="", tags=["buyer-delivery"])
logger = logging.getLogger(__name__)


class DeliveryRequest(BaseModel):
    """Buyer requests sealed delivery of a verified exploit."""
    vulnerability_id: str
    buyer_public_key: str = Field(description="Base64-encoded P-384 DER public key (120 bytes)")


class DeliveryResponse(BaseModel):
    """Sealed delivery — buyer decrypts with their private key."""
    delivery_ciphertext: str  # base64 — AES-256-GCM(K_d, exploit)
    delivery_key_ciphertext: str  # base64 — ECIES(buyer_pub, K_d)
    delivery_hash: str  # SHA-256 commitment
    key_commitment: str  # SHA-256 commitment


@router.post("/request", response_model=DeliveryResponse)
async def request_delivery(
    request: DeliveryRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Request sealed delivery of a verified exploit.

    The exploit is re-encrypted to the buyer's public key inside the enclave
    (or in simulated mode, in-process). The platform never sees the plaintext.

    Prerequisites:
    - Vulnerability must be verified (created via proposal verification)
    - Buyer must provide their P-384 public key for ECIES
    - In production: escrow payment must be confirmed on-chain
    """
    # Look up the listing
    vuln_result = await db.execute(
        select(ZKVulnerability).where(
            ZKVulnerability.id == uuid.UUID(request.vulnerability_id)
        )
    )
    vuln = vuln_result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    if vuln.status != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")
    if vuln.seller_pubkey == pubkey:
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")

    # Find the verified proposal that created this listing
    from ndai.models.verification_proposal import VerificationProposal
    prop_result = await db.execute(
        select(VerificationProposal).where(
            VerificationProposal.created_vuln_id == vuln.id
        )
    )
    proposal = prop_result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=400, detail="No verified proposal linked to this listing")
    if not proposal.sealed_poc and not proposal.poc_script:
        raise HTTPException(status_code=400, detail="No PoC available for delivery")

    # Get the PoC plaintext (in simulated mode, decrypt sealed_poc; in nitro, route to enclave)
    from ndai.config import settings
    if proposal.sealed_poc:
        from ndai.api.routers.enclave import _get_sim_state
        from ndai.enclave.ephemeral_keys import ecies_decrypt
        sim_keypair, _ = _get_sim_state()
        poc_plaintext = ecies_decrypt(sim_keypair.private_key, proposal.sealed_poc)
    else:
        poc_plaintext = proposal.poc_script.encode()

    # Re-encrypt for buyer using SealedDeliveryProtocol
    from ndai.enclave.vuln_verify.sealed_delivery import SealedDeliveryProtocol
    buyer_pubkey_der = base64.b64decode(request.buyer_public_key)
    if len(buyer_pubkey_der) < 120:
        raise HTTPException(status_code=400, detail="Invalid buyer public key (expected P-384 DER, 120 bytes)")

    protocol = SealedDeliveryProtocol()
    delivery = protocol.seal(poc_plaintext, buyer_pubkey_der)

    logger.info(
        "Sealed delivery for vuln %s to buyer %s: hash=%s",
        request.vulnerability_id, pubkey[:16], delivery.delivery_hash[:16],
    )

    return DeliveryResponse(
        delivery_ciphertext=base64.b64encode(delivery.delivery_ciphertext).decode(),
        delivery_key_ciphertext=base64.b64encode(delivery.delivery_key_ciphertext).decode(),
        delivery_hash=delivery.delivery_hash,
        key_commitment=delivery.key_commitment,
    )
