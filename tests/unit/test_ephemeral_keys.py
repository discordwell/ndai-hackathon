"""Unit tests for ephemeral key generation and ECIES encryption."""

import os

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from ndai.enclave.ephemeral_keys import (
    EnclaveKeypair,
    decrypt_api_key,
    ecies_decrypt,
    ecies_encrypt,
    encrypt_api_key,
    generate_keypair,
)


class TestGenerateKeypair:
    def test_generates_p384_key(self):
        """Keypair should use the P-384 curve."""
        kp = generate_keypair()
        assert isinstance(kp.private_key, ec.EllipticCurvePrivateKey)
        assert isinstance(kp.private_key.curve, ec.SECP384R1)

    def test_public_key_der_is_valid(self):
        """The DER encoding should be loadable."""
        kp = generate_keypair()
        loaded = serialization.load_der_public_key(kp.public_key_der)
        assert isinstance(loaded, ec.EllipticCurvePublicKey)

    def test_keypair_is_unique(self):
        """Each call generates a different keypair."""
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        assert kp1.public_key_der != kp2.public_key_der

    def test_public_key_der_length(self):
        """P-384 SubjectPublicKeyInfo DER should be 120 bytes."""
        kp = generate_keypair()
        assert len(kp.public_key_der) == 120

    def test_keypair_is_frozen(self):
        """EnclaveKeypair should be immutable."""
        kp = generate_keypair()
        with pytest.raises(AttributeError):
            kp.api_key = "test"  # type: ignore


class TestECIES:
    def test_roundtrip(self):
        """Encrypt then decrypt should return the original plaintext."""
        kp = generate_keypair()
        plaintext = b"Hello, World! This is a secret."

        encrypted = ecies_encrypt(kp.public_key, plaintext)
        decrypted = ecies_decrypt(kp.private_key, encrypted)

        assert decrypted == plaintext

    def test_roundtrip_empty_message(self):
        """ECIES should handle empty plaintext."""
        kp = generate_keypair()
        encrypted = ecies_encrypt(kp.public_key, b"")
        decrypted = ecies_decrypt(kp.private_key, encrypted)
        assert decrypted == b""

    def test_roundtrip_large_message(self):
        """ECIES should handle large messages."""
        kp = generate_keypair()
        plaintext = os.urandom(10000)
        encrypted = ecies_encrypt(kp.public_key, plaintext)
        decrypted = ecies_decrypt(kp.private_key, encrypted)
        assert decrypted == plaintext

    def test_wrong_key_rejection(self):
        """Decryption with wrong key should fail with InvalidTag."""
        kp1 = generate_keypair()
        kp2 = generate_keypair()

        encrypted = ecies_encrypt(kp1.public_key, b"secret data")

        with pytest.raises(InvalidTag):
            ecies_decrypt(kp2.private_key, encrypted)

    def test_tampered_ciphertext_rejection(self):
        """Tampered ciphertext should fail decryption."""
        kp = generate_keypair()
        encrypted = ecies_encrypt(kp.public_key, b"secret data")

        # Flip a byte in the ciphertext portion
        tampered = bytearray(encrypted)
        tampered[-5] ^= 0xFF
        tampered = bytes(tampered)

        with pytest.raises((InvalidTag, ValueError)):
            ecies_decrypt(kp.private_key, tampered)

    def test_truncated_payload_rejection(self):
        """Truncated payload should raise ValueError."""
        kp = generate_keypair()

        with pytest.raises(ValueError, match="too short"):
            ecies_decrypt(kp.private_key, b"short")

    def test_encrypted_output_contains_ephemeral_key(self):
        """The encrypted output should start with a 120-byte ephemeral public key."""
        kp = generate_keypair()
        encrypted = ecies_encrypt(kp.public_key, b"test")

        # First 120 bytes should be a valid P-384 public key
        ephemeral_der = encrypted[:120]
        loaded = serialization.load_der_public_key(ephemeral_der)
        assert isinstance(loaded, ec.EllipticCurvePublicKey)

    def test_each_encryption_is_unique(self):
        """Same plaintext encrypted twice should produce different ciphertexts."""
        kp = generate_keypair()
        plaintext = b"same message"

        enc1 = ecies_encrypt(kp.public_key, plaintext)
        enc2 = ecies_encrypt(kp.public_key, plaintext)

        # Different ephemeral keys → different ciphertext
        assert enc1 != enc2

        # But both decrypt to the same thing
        assert ecies_decrypt(kp.private_key, enc1) == plaintext
        assert ecies_decrypt(kp.private_key, enc2) == plaintext


class TestAPIKeyHelpers:
    def test_encrypt_decrypt_api_key(self):
        """encrypt_api_key + decrypt_api_key roundtrip."""
        kp = generate_keypair()
        api_key = "sk-test-abc123def456"

        encrypted = encrypt_api_key(kp.public_key_der, api_key)
        decrypted = decrypt_api_key(kp.private_key, encrypted)

        assert decrypted == api_key

    def test_encrypt_api_key_validates_key_type(self):
        """encrypt_api_key should reject non-EC keys."""
        from cryptography.hazmat.primitives.asymmetric import rsa

        rsa_key = rsa.generate_private_key(65537, 2048)
        rsa_der = rsa_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with pytest.raises(ValueError, match="Not an EC public key"):
            encrypt_api_key(rsa_der, "sk-test")

    def test_unicode_api_key(self):
        """API keys with special characters should work."""
        kp = generate_keypair()
        api_key = "sk-ant-api03-abcdef123456-éàü"

        encrypted = encrypt_api_key(kp.public_key_der, api_key)
        decrypted = decrypt_api_key(kp.private_key, encrypted)

        assert decrypted == api_key
