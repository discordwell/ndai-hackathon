"""Sealed exploit delivery — zero-knowledge transfer via TEE re-encryption.

The exploit plaintext ONLY exists inside the Nitro Enclave. This module
re-encrypts it for the buyer using a fresh delivery key, then encrypts
the delivery key to the buyer's public key. The platform operator never
possesses any decryption key.

Protocol:
    1. Seller encrypts exploit with K_s, sends K_s encrypted to enclave (ECIES)
    2. Enclave decrypts K_s → decrypts exploit → verifies PoC
    3. Buyer sends their public key encrypted to enclave (ECIES)
    4. Enclave generates K_d, re-encrypts exploit: C_delivery = AES(K_d, exploit)
    5. Enclave encrypts K_d to buyer: E_key = ECIES(buyer_pub, K_d)
    6. Enclave outputs: C_delivery, E_key, SHA-256 hashes of both
    7. Platform stores ciphertext; on-chain stores hashes
    8. After payment: buyer retrieves C_delivery + E_key, decrypts

What the platform sees: only ciphertext and hashes. Never any key.
"""

import hashlib
import logging
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from cryptography.hazmat.primitives.serialization import load_der_public_key

from ndai.enclave.ephemeral_keys import ecies_decrypt, ecies_encrypt

logger = logging.getLogger(__name__)

AES_KEY_SIZE = 32   # AES-256
GCM_NONCE_SIZE = 12


@dataclass(frozen=True)
class SealedDelivery:
    """Output of the sealed delivery protocol. All fields are ciphertext or hashes."""

    delivery_ciphertext: bytes     # AES-256-GCM(K_d, exploit_plaintext)
    delivery_key_ciphertext: bytes # ECIES(buyer_pub, K_d)
    delivery_hash: str             # SHA-256(delivery_ciphertext) hex
    key_commitment: str            # SHA-256(delivery_key_ciphertext) hex


class SealedDeliveryProtocol:
    """Creates sealed delivery inside the enclave.

    The enclave holds the exploit plaintext in memory (from PoC verification).
    This protocol re-encrypts it for the buyer so the plaintext never
    leaves the enclave.
    """

    def __init__(self, enclave_keypair=None):
        """Initialize with the enclave's ephemeral keypair for ECIES operations."""
        self._keypair = enclave_keypair

    def seal(
        self,
        exploit_plaintext: bytes,
        buyer_public_key_der: bytes,
    ) -> SealedDelivery:
        """Re-encrypt exploit for buyer delivery.

        Args:
            exploit_plaintext: The raw exploit/PoC code (decrypted inside enclave).
            buyer_public_key_der: Buyer's P-384 public key in DER format.

        Returns:
            SealedDelivery with all ciphertext and commitment hashes.
        """
        # 1. Generate fresh delivery key (never leaves enclave in plaintext)
        delivery_key = os.urandom(AES_KEY_SIZE)

        # 2. Encrypt exploit with delivery key (AES-256-GCM)
        nonce = os.urandom(GCM_NONCE_SIZE)
        aes = AESGCM(delivery_key)
        ciphertext = aes.encrypt(nonce, exploit_plaintext, None)
        # Pack as: nonce(12) || ciphertext+tag
        delivery_ciphertext = nonce + ciphertext

        # 3. Encrypt delivery key to buyer's public key (ECIES)
        buyer_public_key = load_der_public_key(buyer_public_key_der)
        delivery_key_ciphertext = ecies_encrypt(buyer_public_key, delivery_key)

        # 4. Compute commitment hashes (for on-chain accountability)
        delivery_hash = hashlib.sha256(delivery_ciphertext).hexdigest()
        key_commitment = hashlib.sha256(delivery_key_ciphertext).hexdigest()

        logger.info(
            "Sealed delivery: payload=%d bytes, delivery_hash=%s, key_commitment=%s",
            len(delivery_ciphertext),
            delivery_hash[:16],
            key_commitment[:16],
        )

        return SealedDelivery(
            delivery_ciphertext=delivery_ciphertext,
            delivery_key_ciphertext=delivery_key_ciphertext,
            delivery_hash=delivery_hash,
            key_commitment=key_commitment,
        )

    def decrypt_seller_payload(self, encrypted_payload: bytes, encrypted_key: bytes) -> bytes:
        """Decrypt the seller's exploit payload inside the enclave.

        Args:
            encrypted_payload: AES-256-GCM(K_s, exploit_plaintext) — nonce(12) || ciphertext+tag
            encrypted_key: ECIES(enclave_pub, K_s) — the seller's key encrypted to enclave

        Returns:
            exploit_plaintext: The raw exploit code.
        """
        if self._keypair is None:
            raise ValueError("No enclave keypair available for decryption")

        # Decrypt seller's key using enclave's ECIES
        seller_key = ecies_decrypt(self._keypair.private_key, encrypted_key)

        # Decrypt exploit using seller's key
        nonce = encrypted_payload[:GCM_NONCE_SIZE]
        ciphertext = encrypted_payload[GCM_NONCE_SIZE:]
        aes = AESGCM(seller_key)
        return aes.decrypt(nonce, ciphertext, None)


def unseal_delivery(
    delivery_ciphertext: bytes,
    delivery_key_ciphertext: bytes,
    buyer_private_key,
) -> bytes:
    """Buyer-side: decrypt the sealed delivery.

    This runs on the BUYER's machine (not in the enclave).

    Args:
        delivery_ciphertext: AES-256-GCM(K_d, exploit) — nonce(12) || ciphertext+tag
        delivery_key_ciphertext: ECIES(buyer_pub, K_d)
        buyer_private_key: Buyer's P-384 private key object

    Returns:
        exploit_plaintext
    """
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes

    # Manually decrypt ECIES (same scheme as ephemeral_keys.py)
    # Format: [ephemeral_pubkey_DER | nonce(12) | ciphertext+tag(16)]
    # The ephemeral pubkey DER for P-384 is 120 bytes
    PUBKEY_DER_SIZE = 120

    ephemeral_pub_der = delivery_key_ciphertext[:PUBKEY_DER_SIZE]
    ecies_nonce = delivery_key_ciphertext[PUBKEY_DER_SIZE:PUBKEY_DER_SIZE + GCM_NONCE_SIZE]
    ecies_ciphertext = delivery_key_ciphertext[PUBKEY_DER_SIZE + GCM_NONCE_SIZE:]

    ephemeral_pub = load_der_public_key(ephemeral_pub_der)
    shared_secret = buyer_private_key.exchange(ec.ECDH(), ephemeral_pub)

    derived_key = HKDF(
        algorithm=hashes.SHA384(),
        length=AES_KEY_SIZE,
        salt=None,
        info=b"ndai-key-delivery",
    ).derive(shared_secret)

    aes = AESGCM(derived_key)
    delivery_key = aes.decrypt(ecies_nonce, ecies_ciphertext, None)

    # Decrypt exploit using delivery key
    nonce = delivery_ciphertext[:GCM_NONCE_SIZE]
    ciphertext = delivery_ciphertext[GCM_NONCE_SIZE:]
    aes2 = AESGCM(delivery_key)
    return aes2.decrypt(nonce, ciphertext, None)


def verify_delivery_commitments(
    delivery_ciphertext: bytes,
    delivery_key_ciphertext: bytes,
    expected_delivery_hash: str,
    expected_key_commitment: str,
) -> bool:
    """Verify that the delivered ciphertext matches on-chain commitments.

    Can be run by anyone (buyer, auditor) — only needs the ciphertext and hashes.
    """
    actual_delivery_hash = hashlib.sha256(delivery_ciphertext).hexdigest()
    actual_key_commitment = hashlib.sha256(delivery_key_ciphertext).hexdigest()
    return (
        actual_delivery_hash == expected_delivery_hash
        and actual_key_commitment == expected_key_commitment
    )
