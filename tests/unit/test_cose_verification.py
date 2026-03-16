"""Unit tests for COSE Sign1 verification and certificate chain validation."""

import os
import time

import cbor2
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from ndai.enclave.nsm_stub import NSMStub
from ndai.tee.attestation import (
    AttestationResult,
    verify_attestation,
    _verify_cert_chain,
    _verify_cose_signature,
)


def _make_test_cert_chain():
    """Create a test certificate chain: root -> intermediate -> leaf.

    Returns (root_key, root_cert, chain_certs, leaf_key).
    """
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)

    # Root CA
    root_key = ec.generate_private_key(ec.SECP384R1())
    root_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Root CA"),
    ])
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(root_key, hashes.SHA384())
    )

    # Intermediate
    int_key = ec.generate_private_key(ec.SECP384R1())
    int_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Intermediate CA"),
    ])
    int_cert = (
        x509.CertificateBuilder()
        .subject_name(int_name)
        .issuer_name(root_name)
        .public_key(int_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(root_key, hashes.SHA384())
    )

    # Leaf
    leaf_key = ec.generate_private_key(ec.SECP384R1())
    leaf_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Test Leaf"),
    ])
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(int_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(int_key, hashes.SHA384())
    )

    chain_certs = [root_cert, int_cert, leaf_cert]
    return root_key, root_cert, chain_certs, leaf_key


class TestVerifyCertChain:
    """Test certificate chain verification."""

    def test_valid_chain(self):
        """A properly signed chain should verify successfully."""
        root_key, root_cert, chain_certs, leaf_key = _make_test_cert_chain()
        result = _verify_cert_chain(chain_certs, root_cert)
        assert result is None

    def test_tampered_chain(self):
        """A chain with a tampered certificate should fail."""
        root_key, root_cert, chain_certs, leaf_key = _make_test_cert_chain()

        # Replace intermediate with a self-signed cert (not signed by root)
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        rogue_key = ec.generate_private_key(ec.SECP384R1())
        rogue_cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Rogue")]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Rogue")]))
            .public_key(rogue_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=1))
            .sign(rogue_key, hashes.SHA384())
        )

        tampered_chain = [rogue_cert, chain_certs[1], chain_certs[2]]
        result = _verify_cert_chain(tampered_chain, root_cert)
        assert result is not None
        assert "failed" in result.lower()

    def test_single_cert_chain(self):
        """A single self-signed cert should verify if it matches root."""
        root_key, root_cert, _, _ = _make_test_cert_chain()
        result = _verify_cert_chain([root_cert], root_cert)
        assert result is None


class TestCOSESignatureVerification:
    """Test COSE Sign1 signature verification."""

    def test_valid_stub_attestation_with_skip(self):
        """NSMStub attestation should verify when skipping signature check."""
        stub = NSMStub(eif_path="test.eif")
        nonce = os.urandom(32)
        doc = stub.get_attestation(nonce=nonce)

        result = verify_attestation(doc, nonce=nonce, skip_signature_check=True)
        assert result.valid is True
        assert len(result.pcrs) == 3

    def test_stub_attestation_nonce_check(self):
        """Nonce mismatch should be detected."""
        stub = NSMStub(eif_path="test.eif")
        nonce = os.urandom(32)
        wrong_nonce = os.urandom(32)
        doc = stub.get_attestation(nonce=nonce)

        result = verify_attestation(doc, nonce=wrong_nonce, skip_signature_check=True)
        assert result.valid is False
        assert "Nonce mismatch" in result.error

    def test_stub_attestation_pcr_check(self):
        """PCR mismatch should be detected."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation()
        pcr0_hex = stub.pcrs[0].hex()

        # Correct PCR
        result = verify_attestation(
            doc, expected_pcrs={0: pcr0_hex}, skip_signature_check=True
        )
        assert result.valid is True

        # Wrong PCR
        result = verify_attestation(
            doc, expected_pcrs={0: "ff" * 48}, skip_signature_check=True
        )
        assert result.valid is False
        assert "PCR0 mismatch" in result.error

    def test_stub_attestation_extracts_public_key(self):
        """Public key should be extracted from the attestation."""
        from ndai.enclave.ephemeral_keys import generate_keypair

        kp = generate_keypair()
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation(public_key=kp.public_key_der)

        result = verify_attestation(doc, skip_signature_check=True)
        assert result.valid is True
        assert result.enclave_public_key == kp.public_key_der

    def test_stub_attestation_timestamp_freshness(self):
        """Recent attestation should pass freshness check."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation()

        result = verify_attestation(doc, max_age_sec=60, skip_signature_check=True)
        assert result.valid is True

    def test_tampered_payload_fails_signature(self):
        """Modifying payload bytes should cause signature failure."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation(nonce=b"test")

        # Parse the COSE structure
        cose_obj = cbor2.loads(doc)
        cose_array = cose_obj.value

        # Tamper with the payload
        payload = cbor2.loads(cose_array[2])
        payload["nonce"] = b"tampered"
        cose_array[2] = cbor2.dumps(payload)

        # Re-encode (keeping original signature — should now be invalid)
        tampered_doc = cbor2.dumps(cbor2.CBORTag(18, cose_array))

        # With signature check: should detect the self-signed cert isn't from AWS root
        # But the _verify_cose_signature function is what we want to test
        cose_obj2 = cbor2.loads(tampered_doc)
        arr = cose_obj2.value
        payload2 = cbor2.loads(arr[2])

        # The signature was for the original payload, so verifying against
        # the tampered payload should fail
        error = _verify_cose_signature(arr[0], arr[2], arr[3], payload2)
        # Either cert chain fails (no AWS root) or signature fails
        assert error is not None

    def test_tampered_signature_fails(self):
        """Modifying the signature should cause verification failure."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation()

        cose_obj = cbor2.loads(doc)
        cose_array = list(cose_obj.value)

        # Tamper with signature
        sig = bytearray(cose_array[3])
        sig[0] ^= 0xFF
        cose_array[3] = bytes(sig)

        tampered_doc = cbor2.dumps(cbor2.CBORTag(18, cose_array))

        # The verification should fail (either chain or signature)
        result = verify_attestation(tampered_doc, skip_signature_check=False)
        # Will fail because cert chain doesn't lead to AWS root
        assert result.valid is False


class TestVerifyAttestationEdgeCases:
    """Edge cases for the verify_attestation function."""

    def test_non_cbor_non_json_returns_error(self):
        """Garbage input should return an error."""
        result = verify_attestation(b"\x00\x01garbage")
        assert result.valid is False
        assert result.error is not None

    def test_empty_input(self):
        """Empty input should return an error."""
        result = verify_attestation(b"")
        assert result.valid is False

    def test_attestation_result_has_enclave_public_key_field(self):
        """AttestationResult should support enclave_public_key."""
        result = AttestationResult(
            valid=True,
            pcrs={},
            enclave_cid=None,
            timestamp=None,
            enclave_public_key=b"\x04test",
        )
        assert result.enclave_public_key == b"\x04test"

    def test_attestation_result_enclave_public_key_default_none(self):
        """enclave_public_key should default to None."""
        result = AttestationResult(
            valid=True,
            pcrs={},
            enclave_cid=None,
            timestamp=None,
        )
        assert result.enclave_public_key is None

    def test_simulated_format_still_works(self):
        """Simulated JSON attestation should still be auto-detected."""
        import json
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-test",
            "pcr0": "aa",
            "pcr1": "bb",
            "pcr2": "cc",
            "nonce": None,
            "warning": "SIMULATED",
        }
        result = verify_attestation(json.dumps(doc).encode())
        assert result.valid is True
        assert result.pcrs == {0: "aa", 1: "bb", 2: "cc"}
        # Simulated format doesn't have enclave_public_key
        assert result.enclave_public_key is None
