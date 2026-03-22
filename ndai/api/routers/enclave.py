"""Enclave attestation endpoint — sellers verify the TEE before encrypting their PoC."""

import base64
import logging

from fastapi import APIRouter, Query

router = APIRouter(prefix="", tags=["enclave"])
logger = logging.getLogger(__name__)

# Module-level simulated enclave state (shared across requests).
# In simulated mode, we maintain a single keypair so sellers can encrypt
# to it and the verification pipeline can decrypt with the same key.
# In nitro mode, this is unused — attestation comes from the real enclave.
_sim_keypair = None
_sim_nsm = None


def _get_sim_state():
    """Lazy-init simulated enclave keypair + NSM stub."""
    global _sim_keypair, _sim_nsm
    if _sim_keypair is None:
        from ndai.enclave.ephemeral_keys import generate_keypair
        _sim_keypair = generate_keypair()
        logger.info("Initialized simulated enclave keypair (%d bytes DER)", len(_sim_keypair.public_key_der))
    if _sim_nsm is None:
        from ndai.enclave.nsm_stub import NSMStub
        _sim_nsm = NSMStub()
    return _sim_keypair, _sim_nsm


@router.get("/attestation")
async def get_attestation(
    nonce: str = Query(default="", description="Hex-encoded nonce for freshness (16-64 bytes)"),
):
    """Return the verification enclave's attestation document.

    The attestation proves:
    - PCR0: hash of the enclave code (verifiable against public repo build)
    - Public key: the enclave's ephemeral P-384 key (for ECIES encryption)
    - Nonce: freshness proof (prevents replay)

    In Nitro mode: signed by AWS hardware (COSE Sign1, cert chain → AWS Root CA).
    In simulated mode: self-signed (no security guarantees, same API surface).

    Sellers use this to verify the enclave before encrypting their PoC.
    """
    from ndai.config import settings

    nonce_bytes = bytes.fromhex(nonce) if nonce else b""

    if settings.tee_mode == "nitro":
        return await _get_nitro_attestation(nonce_bytes)
    else:
        return _get_simulated_attestation(nonce_bytes)


def _get_simulated_attestation(nonce_bytes: bytes) -> dict:
    """Generate a self-signed attestation doc using the module-level test keypair."""
    keypair, nsm = _get_sim_state()

    attestation_doc = nsm.get_attestation(
        public_key=keypair.public_key_der,
        nonce=nonce_bytes or None,
    )

    return {
        "attestation_doc": base64.b64encode(attestation_doc).decode(),
        "enclave_public_key": base64.b64encode(keypair.public_key_der).decode(),
        "pcr0": nsm._pcrs[0].hex() if hasattr(nsm, '_pcrs') else "simulated",
        "format": "cose_sign1",
        "mode": "simulated",
    }


async def _get_nitro_attestation(nonce_bytes: bytes) -> dict:
    """Get attestation from a running Nitro enclave."""
    from ndai.tee.nitro_provider import NitroEnclaveProvider
    from ndai.tee.attestation import verify_attestation

    provider = NitroEnclaveProvider()

    # Find running enclave or indicate none is available
    enclaves = await provider.list_enclaves()
    if not enclaves:
        return {
            "error": "No enclave running. Start a verification to launch one.",
            "format": "none",
            "mode": "nitro",
        }

    enclave_id = enclaves[0]["enclave_id"]

    # Request attestation from the enclave
    await provider.send_message(enclave_id, {
        "action": "get_attestation",
        "nonce": nonce_bytes.hex() if nonce_bytes else "",
    })
    response = await provider.receive_message(enclave_id)

    if response.get("status") != "ok":
        return {"error": response.get("error", "Attestation failed"), "mode": "nitro"}

    attestation_doc_b64 = response["attestation_doc"]
    attestation_doc = base64.b64decode(attestation_doc_b64)

    # Verify and extract public key
    result = verify_attestation(attestation_doc, nonce=nonce_bytes or None)

    return {
        "attestation_doc": attestation_doc_b64,
        "enclave_public_key": base64.b64encode(result.enclave_public_key).decode() if result.enclave_public_key else None,
        "pcr0": result.pcrs.get(0, "unknown"),
        "format": "cose_sign1",
        "mode": "nitro",
        "valid": result.valid,
    }
