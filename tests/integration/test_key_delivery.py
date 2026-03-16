"""Integration tests for the attestation → key delivery → decryption flow.

Tests the complete secure key delivery pipeline:
1. Enclave generates ephemeral keypair
2. Enclave produces attestation with embedded public key (via NSMStub)
3. Parent verifies attestation and extracts public key
4. Parent encrypts API key with ECIES
5. Enclave decrypts API key

All tests run locally without Nitro hardware.
"""

import base64
import os

import cbor2
import pytest

from ndai.enclave.ephemeral_keys import (
    decrypt_api_key,
    ecies_decrypt,
    ecies_encrypt,
    encrypt_api_key,
    generate_keypair,
)
from ndai.enclave.nsm_stub import NSMStub
from ndai.tee.attestation import verify_attestation


class TestKeyDeliveryFlow:
    """End-to-end key delivery through attestation."""

    def test_full_flow(self):
        """Complete attestation → key delivery → decryption."""
        # Step 1: Enclave generates keypair
        kp = generate_keypair()

        # Step 2: Enclave produces attestation (via NSMStub)
        stub = NSMStub(eif_path="test.eif")
        nonce = os.urandom(32)
        attestation_doc = stub.get_attestation(
            public_key=kp.public_key_der,
            nonce=nonce,
        )

        # Step 3: Parent verifies attestation
        result = verify_attestation(
            attestation_doc,
            nonce=nonce,
            skip_signature_check=True,  # Stub cert chain won't match AWS root
        )
        assert result.valid is True
        assert result.enclave_public_key is not None
        assert result.enclave_public_key == kp.public_key_der

        # Step 4: Parent encrypts API key using the enclave's public key
        api_key = "sk-ant-api03-real-production-key-abc123"
        encrypted = encrypt_api_key(result.enclave_public_key, api_key)

        # Step 5: Enclave decrypts
        decrypted = decrypt_api_key(kp.private_key, encrypted)
        assert decrypted == api_key

    def test_flow_with_pcr_verification(self):
        """Key delivery with PCR verification of the attestation."""
        kp = generate_keypair()
        stub = NSMStub(eif_path="prod-image.eif")
        nonce = os.urandom(32)

        attestation_doc = stub.get_attestation(
            public_key=kp.public_key_der,
            nonce=nonce,
        )

        # Get expected PCRs from the stub
        expected_pcrs = {i: stub.pcrs[i].hex() for i in range(3)}

        result = verify_attestation(
            attestation_doc,
            nonce=nonce,
            expected_pcrs=expected_pcrs,
            skip_signature_check=True,
        )
        assert result.valid is True

        # Deliver key
        encrypted = encrypt_api_key(result.enclave_public_key, "sk-test-key")
        decrypted = decrypt_api_key(kp.private_key, encrypted)
        assert decrypted == "sk-test-key"

    def test_wrong_pcrs_blocks_key_delivery(self):
        """Wrong PCR values should prevent key delivery."""
        kp = generate_keypair()
        stub = NSMStub(eif_path="test.eif")
        nonce = os.urandom(32)

        attestation_doc = stub.get_attestation(
            public_key=kp.public_key_der,
            nonce=nonce,
        )

        # Use wrong PCRs
        wrong_pcrs = {0: "ff" * 48}
        result = verify_attestation(
            attestation_doc,
            nonce=nonce,
            expected_pcrs=wrong_pcrs,
            skip_signature_check=True,
        )
        assert result.valid is False
        assert "PCR0 mismatch" in result.error

        # Parent should NOT deliver key since attestation failed
        # (This is an application-level check, not crypto)

    def test_stale_nonce_blocks_key_delivery(self):
        """Wrong nonce should prevent key delivery."""
        kp = generate_keypair()
        stub = NSMStub(eif_path="test.eif")
        nonce = os.urandom(32)
        wrong_nonce = os.urandom(32)

        attestation_doc = stub.get_attestation(
            public_key=kp.public_key_der,
            nonce=nonce,
        )

        result = verify_attestation(
            attestation_doc,
            nonce=wrong_nonce,
            skip_signature_check=True,
        )
        assert result.valid is False
        assert "Nonce mismatch" in result.error

    def test_key_delivery_different_enclave_cannot_decrypt(self):
        """A different enclave's keypair cannot decrypt the delivered key."""
        from cryptography.exceptions import InvalidTag

        # Enclave A creates keypair and attestation
        kp_a = generate_keypair()
        stub = NSMStub(eif_path="test.eif")
        attestation_doc = stub.get_attestation(public_key=kp_a.public_key_der)

        result = verify_attestation(attestation_doc, skip_signature_check=True)
        assert result.valid is True

        # Parent encrypts for enclave A
        encrypted = encrypt_api_key(result.enclave_public_key, "secret-key")

        # Enclave B tries to decrypt
        kp_b = generate_keypair()
        with pytest.raises(InvalidTag):
            decrypt_api_key(kp_b.private_key, encrypted)

    def test_base64_transport(self):
        """Key delivery over base64 transport (as used by vsock JSON framing)."""
        kp = generate_keypair()
        api_key = "sk-ant-production-key-xyz789"

        # Encrypt
        encrypted = encrypt_api_key(kp.public_key_der, api_key)

        # Transport as base64 (simulating JSON framing)
        b64_payload = base64.b64encode(encrypted).decode("ascii")
        assert isinstance(b64_payload, str)

        # Decode and decrypt
        recovered_payload = base64.b64decode(b64_payload)
        decrypted = decrypt_api_key(kp.private_key, recovered_payload)
        assert decrypted == api_key


class TestAttestationPublicKeyExtraction:
    """Test that public keys are correctly embedded and extracted."""

    def test_public_key_roundtrip_through_attestation(self):
        """Public key embedded in attestation should be extractable."""
        kp = generate_keypair()
        stub = NSMStub(eif_path="test.eif")

        doc = stub.get_attestation(public_key=kp.public_key_der)

        # Parse manually to verify
        cose_obj = cbor2.loads(doc)
        payload = cbor2.loads(cose_obj.value[2])

        assert "public_key" in payload
        assert payload["public_key"] == kp.public_key_der

        # Also verify via verify_attestation
        result = verify_attestation(doc, skip_signature_check=True)
        assert result.enclave_public_key == kp.public_key_der

    def test_no_public_key_in_attestation(self):
        """Attestation without public key should have None."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation()  # No public_key

        result = verify_attestation(doc, skip_signature_check=True)
        assert result.valid is True
        assert result.enclave_public_key is None
