"""Ephemeral EC P-384 keypair for secure API key delivery.

Generated fresh on each enclave startup. The public key is embedded in the
NSM attestation document so the parent can verify it belongs to a legitimate
enclave before encrypting the API key.

Key delivery flow:
    1. Enclave generates P-384 keypair
    2. Public key DER is included in attestation request to NSM
    3. Parent verifies attestation, extracts public key
    4. Parent encrypts API key using ECIES (ECDH + HKDF + AES-256-GCM)
    5. Enclave decrypts with private key

ECIES scheme:
    - ECDH: parent ephemeral key + enclave public key → shared secret
    - KDF: HKDF-SHA384 with info="ndai-key-delivery"
    - Encryption: AES-256-GCM with derived key
    - Transmitted: [parent_ephemeral_pubkey_DER | nonce(12) | ciphertext | tag(16)]
"""

import logging
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

# ECIES constants
ECIES_INFO = b"ndai-key-delivery"
AES_KEY_SIZE = 32  # AES-256
GCM_NONCE_SIZE = 12
GCM_TAG_SIZE = 16


@dataclass(frozen=True)
class EnclaveKeypair:
    """Enclave's ephemeral P-384 keypair."""

    private_key: ec.EllipticCurvePrivateKey
    public_key: ec.EllipticCurvePublicKey
    public_key_der: bytes  # SubjectPublicKeyInfo DER encoding


def generate_keypair() -> EnclaveKeypair:
    """Generate a fresh P-384 keypair for this enclave session.

    Returns:
        EnclaveKeypair with private key, public key, and DER-encoded public key.
    """
    private_key = ec.generate_private_key(ec.SECP384R1())
    public_key = private_key.public_key()
    public_key_der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    logger.info("Generated ephemeral P-384 keypair (%d bytes DER)", len(public_key_der))
    return EnclaveKeypair(
        private_key=private_key,
        public_key=public_key,
        public_key_der=public_key_der,
    )


def sign_data(private_key: ec.EllipticCurvePrivateKey, data: bytes) -> bytes:
    """Sign data using P-384 ECDSA.

    Args:
        private_key: The enclave's P-384 private key.
        data: Bytes to sign.

    Returns:
        DER-encoded ECDSA signature.
    """
    return private_key.sign(data, ec.ECDSA(hashes.SHA384()))


def verify_signature(
    public_key: ec.EllipticCurvePublicKey, signature: bytes, data: bytes
) -> bool:
    """Verify a P-384 ECDSA signature.

    Returns:
        True if valid, False otherwise.
    """
    try:
        public_key.verify(signature, data, ec.ECDSA(hashes.SHA384()))
        return True
    except Exception:
        return False


def _ecdh_derive_key(
    private_key: ec.EllipticCurvePrivateKey,
    peer_public_key: ec.EllipticCurvePublicKey,
) -> bytes:
    """Derive an AES-256 key from ECDH shared secret using HKDF-SHA384."""
    shared_secret = private_key.exchange(ec.ECDH(), peer_public_key)
    derived_key = HKDF(
        algorithm=hashes.SHA384(),
        length=AES_KEY_SIZE,
        salt=None,
        info=ECIES_INFO,
    ).derive(shared_secret)
    return derived_key


def ecies_encrypt(
    recipient_public_key: ec.EllipticCurvePublicKey,
    plaintext: bytes,
) -> bytes:
    """Encrypt data using ECIES for the enclave's public key.

    Called by the parent after verifying attestation.

    Args:
        recipient_public_key: The enclave's P-384 public key (from attestation).
        plaintext: Data to encrypt (e.g., API key bytes).

    Returns:
        Encrypted payload: [ephemeral_pubkey_DER(120) | nonce(12) | ciphertext+tag]
    """
    # Generate ephemeral keypair for this encryption
    ephemeral_key = ec.generate_private_key(ec.SECP384R1())
    ephemeral_pubkey_der = ephemeral_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Derive shared key via ECDH
    aes_key = _ecdh_derive_key(ephemeral_key, recipient_public_key)

    # Encrypt with AES-256-GCM
    nonce = os.urandom(GCM_NONCE_SIZE)
    aesgcm = AESGCM(aes_key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, None)

    # Pack: ephemeral_pubkey_DER | nonce | ciphertext+tag
    return ephemeral_pubkey_der + nonce + ciphertext_and_tag


def ecies_decrypt(
    private_key: ec.EllipticCurvePrivateKey,
    encrypted_payload: bytes,
) -> bytes:
    """Decrypt ECIES-encrypted data using the enclave's private key.

    Called by the enclave to recover the API key.

    Args:
        private_key: The enclave's P-384 private key.
        encrypted_payload: Output from ecies_encrypt().

    Returns:
        Decrypted plaintext bytes.

    Raises:
        ValueError: If the payload is malformed.
        cryptography.exceptions.InvalidTag: If decryption fails (wrong key or tampered).
    """
    # P-384 SubjectPublicKeyInfo DER is 120 bytes
    # (algorithm OID + curve OID + 97-byte uncompressed point)
    # But the exact size depends on encoding; find it by parsing
    min_size = GCM_NONCE_SIZE + GCM_TAG_SIZE  # Tag only, ciphertext may be empty
    if len(encrypted_payload) < 120 + min_size:
        raise ValueError(
            f"ECIES payload too short: {len(encrypted_payload)} bytes "
            f"(minimum {120 + min_size})"
        )

    # Parse the ephemeral public key DER
    # P-384 SubjectPublicKeyInfo DER is exactly 120 bytes
    ephemeral_pubkey_der = encrypted_payload[:120]
    remaining = encrypted_payload[120:]

    try:
        ephemeral_public_key = serialization.load_der_public_key(ephemeral_pubkey_der)
    except Exception as exc:
        raise ValueError(f"Failed to parse ephemeral public key: {exc}") from exc

    if not isinstance(ephemeral_public_key, ec.EllipticCurvePublicKey):
        raise ValueError("Ephemeral key is not an EC public key")

    # Derive shared key
    aes_key = _ecdh_derive_key(private_key, ephemeral_public_key)

    # Extract nonce and ciphertext+tag
    nonce = remaining[:GCM_NONCE_SIZE]
    ciphertext_and_tag = remaining[GCM_NONCE_SIZE:]

    # Decrypt
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ciphertext_and_tag, None)


def encrypt_api_key(
    enclave_public_key_der: bytes,
    api_key: str,
) -> bytes:
    """Convenience: encrypt an API key string for delivery to the enclave.

    Args:
        enclave_public_key_der: DER-encoded P-384 public key from attestation.
        api_key: The API key string to encrypt.

    Returns:
        ECIES-encrypted payload bytes.
    """
    public_key = serialization.load_der_public_key(enclave_public_key_der)
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError("Not an EC public key")
    return ecies_encrypt(public_key, api_key.encode("utf-8"))


def decrypt_api_key(
    private_key: ec.EllipticCurvePrivateKey,
    encrypted_payload: bytes,
) -> str:
    """Convenience: decrypt an API key inside the enclave.

    Args:
        private_key: The enclave's P-384 private key.
        encrypted_payload: ECIES-encrypted payload from parent.

    Returns:
        The decrypted API key string.
    """
    plaintext = ecies_decrypt(private_key, encrypted_payload)
    return plaintext.decode("utf-8")
