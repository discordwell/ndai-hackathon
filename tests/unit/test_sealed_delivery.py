"""Tests for sealed exploit delivery — the core cryptographic protocol.

Proves:
1. Seal → unseal round-trip works (buyer recovers exploit)
2. Platform operator CANNOT decrypt any output
3. Hash commitments match and are verifiable
4. Different buyers get different ciphertext (no key reuse)
5. Tampered ciphertext is detected
"""

import os

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ndai.enclave.ephemeral_keys import (
    EnclaveKeypair,
    ecies_encrypt,
    generate_keypair,
)
from ndai.enclave.vuln_verify.sealed_delivery import (
    SealedDelivery,
    SealedDeliveryProtocol,
    unseal_delivery,
    verify_delivery_commitments,
)


SAMPLE_EXPLOIT = (
    b"#!/bin/bash\n"
    b"# CVE-2024-XXXX PoC - buffer overflow in mod_proxy\n"
    b"curl -s http://localhost/ -H 'Content-Length: 2147483648'\n"
    b"cat /var/lib/ndai-oracle/ace_canary\n"
)


def _generate_buyer_keypair():
    """Generate a P-384 keypair for the buyer (client-side)."""
    private_key = ec.generate_private_key(ec.SECP384R1())
    public_key = private_key.public_key()
    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_key_der


class TestSealUnsealRoundTrip:
    """Prove the buyer can recover the exploit after payment."""

    def test_basic_round_trip(self):
        enclave_kp = generate_keypair()
        buyer_priv, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Buyer decrypts
        recovered = unseal_delivery(
            sealed.delivery_ciphertext,
            sealed.delivery_key_ciphertext,
            buyer_priv,
        )
        assert recovered == SAMPLE_EXPLOIT

    def test_large_exploit(self):
        """Works with large payloads (1MB)."""
        enclave_kp = generate_keypair()
        buyer_priv, buyer_pub_der = _generate_buyer_keypair()
        large_payload = os.urandom(1024 * 1024)  # 1MB

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(large_payload, buyer_pub_der)

        recovered = unseal_delivery(
            sealed.delivery_ciphertext,
            sealed.delivery_key_ciphertext,
            buyer_priv,
        )
        assert recovered == large_payload

    def test_empty_exploit(self):
        enclave_kp = generate_keypair()
        buyer_priv, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(b"", buyer_pub_der)

        recovered = unseal_delivery(
            sealed.delivery_ciphertext,
            sealed.delivery_key_ciphertext,
            buyer_priv,
        )
        assert recovered == b""


class TestPlatformCannotDecrypt:
    """Prove the platform operator cannot access the exploit."""

    def test_delivery_ciphertext_is_not_plaintext(self):
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Platform sees delivery_ciphertext but it's AES-GCM encrypted
        assert SAMPLE_EXPLOIT not in sealed.delivery_ciphertext
        assert b"curl" not in sealed.delivery_ciphertext
        assert b"ace_canary" not in sealed.delivery_ciphertext

    def test_delivery_key_ciphertext_is_opaque(self):
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Platform sees delivery_key_ciphertext but can't extract K_d
        # It's ECIES encrypted to buyer's key — at least 148 bytes overhead
        assert len(sealed.delivery_key_ciphertext) > 32  # K_d is 32 bytes, ECIES adds overhead

    def test_wrong_private_key_fails(self):
        """A different private key (e.g., platform's) cannot decrypt."""
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Platform generates their own key and tries to decrypt
        platform_priv = ec.generate_private_key(ec.SECP384R1())
        with pytest.raises(Exception):  # ECIES decryption will fail (wrong key)
            unseal_delivery(
                sealed.delivery_ciphertext,
                sealed.delivery_key_ciphertext,
                platform_priv,
            )

    def test_enclave_key_cannot_decrypt_delivery(self):
        """Even the enclave's own key cannot decrypt the buyer's delivery."""
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Try to decrypt with the enclave's key (not the buyer's)
        with pytest.raises(Exception):
            unseal_delivery(
                sealed.delivery_ciphertext,
                sealed.delivery_key_ciphertext,
                enclave_kp.private_key,
            )


class TestHashCommitments:
    """Prove on-chain commitments match and detect tampering."""

    def test_commitments_verify(self):
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        assert verify_delivery_commitments(
            sealed.delivery_ciphertext,
            sealed.delivery_key_ciphertext,
            sealed.delivery_hash,
            sealed.key_commitment,
        )

    def test_tampered_ciphertext_detected(self):
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Tamper with delivery ciphertext
        tampered = bytearray(sealed.delivery_ciphertext)
        tampered[20] ^= 0xFF
        assert not verify_delivery_commitments(
            bytes(tampered),
            sealed.delivery_key_ciphertext,
            sealed.delivery_hash,
            sealed.key_commitment,
        )

    def test_tampered_key_detected(self):
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Tamper with key ciphertext
        tampered = bytearray(sealed.delivery_key_ciphertext)
        tampered[20] ^= 0xFF
        assert not verify_delivery_commitments(
            sealed.delivery_ciphertext,
            bytes(tampered),
            sealed.delivery_hash,
            sealed.key_commitment,
        )

    def test_hashes_are_hex_sha256(self):
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        assert len(sealed.delivery_hash) == 64  # SHA-256 hex
        assert len(sealed.key_commitment) == 64


class TestKeyIsolation:
    """Prove different sealing runs produce different keys."""

    def test_different_delivery_keys_each_seal(self):
        enclave_kp = generate_keypair()
        _, buyer_pub_der = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed1 = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)
        sealed2 = protocol.seal(SAMPLE_EXPLOIT, buyer_pub_der)

        # Same plaintext, different K_d → different ciphertext
        assert sealed1.delivery_ciphertext != sealed2.delivery_ciphertext
        assert sealed1.delivery_hash != sealed2.delivery_hash

    def test_different_buyers_different_key_ciphertext(self):
        enclave_kp = generate_keypair()
        _, buyer1_pub = _generate_buyer_keypair()
        _, buyer2_pub = _generate_buyer_keypair()

        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        sealed1 = protocol.seal(SAMPLE_EXPLOIT, buyer1_pub)
        sealed2 = protocol.seal(SAMPLE_EXPLOIT, buyer2_pub)

        # Different buyer keys → different encrypted delivery keys
        assert sealed1.delivery_key_ciphertext != sealed2.delivery_key_ciphertext


class TestSellerDecryption:
    """Prove the enclave can decrypt the seller's payload."""

    def test_decrypt_seller_payload(self):
        enclave_kp = generate_keypair()

        # Seller encrypts exploit with their own key, then encrypts that key to enclave
        seller_key = os.urandom(32)
        nonce = os.urandom(12)
        aes = AESGCM(seller_key)
        encrypted_exploit = nonce + aes.encrypt(nonce, SAMPLE_EXPLOIT, None)

        # Seller encrypts K_s to enclave
        encrypted_seller_key = ecies_encrypt(enclave_kp.public_key, seller_key)

        # Enclave decrypts
        protocol = SealedDeliveryProtocol(enclave_keypair=enclave_kp)
        recovered = protocol.decrypt_seller_payload(encrypted_exploit, encrypted_seller_key)
        assert recovered == SAMPLE_EXPLOIT
