"""Unit tests for the NSM device interface and NSMStub."""

import os
import struct
from unittest.mock import MagicMock, patch

import cbor2
import pytest

from ndai.enclave.nsm import NSMDevice, NSMError, is_nsm_available
from ndai.enclave.nsm_stub import NSMStub


class TestNSMDevice:
    """Test the real NSM device interface (with mocked /dev/nsm)."""

    def test_ioctl_cmd_computation(self):
        """The ioctl command should be deterministic."""
        cmd = NSMDevice._ioctl_cmd()
        assert isinstance(cmd, int)
        assert cmd > 0

    def test_open_device_not_found(self):
        """Opening a non-existent device path raises NSMError."""
        nsm = NSMDevice(device_path="/dev/nonexistent_nsm_test")
        with pytest.raises(NSMError, match="Failed to open"):
            nsm.open()

    def test_context_manager(self):
        """Context manager opens and closes the device."""
        nsm = NSMDevice(device_path="/dev/nonexistent_nsm_test")
        with pytest.raises(NSMError):
            with nsm:
                pass

    def test_get_attestation_builds_correct_cbor_request(self):
        """Verify the CBOR request structure sent to /dev/nsm."""
        nsm = NSMDevice()
        nsm._fd = 999  # Fake fd

        nonce = b"\x01\x02\x03\x04"
        pubkey = b"\x05\x06\x07\x08"
        user_data = b"\x09\x0a"

        captured_cbor = {}

        def mock_ioctl_request(request_cbor):
            # Decode the request to verify structure
            request = cbor2.loads(request_cbor)
            captured_cbor.update(request)
            # Return a valid response
            response = {"Attestation": {"document": b"fake_attestation_doc"}}
            return cbor2.dumps(response)

        nsm._ioctl_request = mock_ioctl_request

        result = nsm.get_attestation(
            public_key=pubkey, nonce=nonce, user_data=user_data
        )

        assert result == b"fake_attestation_doc"
        assert "Attestation" in captured_cbor
        att_req = captured_cbor["Attestation"]
        assert att_req["public_key"] == pubkey
        assert att_req["nonce"] == nonce
        assert att_req["user_data"] == user_data

    def test_get_attestation_no_optional_fields(self):
        """Optional fields are omitted when not provided."""
        nsm = NSMDevice()
        nsm._fd = 999

        captured_cbor = {}

        def mock_ioctl_request(request_cbor):
            request = cbor2.loads(request_cbor)
            captured_cbor.update(request)
            response = {"Attestation": {"document": b"doc"}}
            return cbor2.dumps(response)

        nsm._ioctl_request = mock_ioctl_request
        nsm.get_attestation()

        att_req = captured_cbor["Attestation"]
        assert "public_key" not in att_req
        assert "nonce" not in att_req
        assert "user_data" not in att_req

    def test_parse_attestation_response_error(self):
        """NSM error responses raise NSMError."""
        nsm = NSMDevice()
        response_cbor = cbor2.dumps({"Error": "InvalidArgument"})
        with pytest.raises(NSMError, match="InvalidArgument"):
            nsm._parse_attestation_response(response_cbor)

    def test_parse_attestation_response_missing_document(self):
        """Missing document field raises NSMError."""
        nsm = NSMDevice()
        response_cbor = cbor2.dumps({"Attestation": {}})
        with pytest.raises(NSMError, match="missing 'document'"):
            nsm._parse_attestation_response(response_cbor)

    def test_parse_attestation_response_success(self):
        """Successful response returns the document bytes."""
        nsm = NSMDevice()
        doc = b"\x00\x01\x02"
        response_cbor = cbor2.dumps({"Attestation": {"document": doc}})
        result = nsm._parse_attestation_response(response_cbor)
        assert result == doc


class TestIsNsmAvailable:
    def test_returns_false_on_dev_machine(self):
        """On a non-Nitro machine, /dev/nsm doesn't exist."""
        # This test only makes sense outside a Nitro Enclave
        if not os.path.exists("/dev/nsm"):
            assert is_nsm_available() is False

    def test_returns_true_when_device_exists(self):
        with patch("ndai.enclave.nsm.os.path.exists", return_value=True):
            assert is_nsm_available() is True


class TestNSMStub:
    """Test the simulated NSM for local development."""

    def test_generates_valid_cose_sign1(self):
        """Stub output should be parseable as COSE Sign1."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation(nonce=b"test-nonce")

        cose_obj = cbor2.loads(doc)
        assert hasattr(cose_obj, "tag")
        assert cose_obj.tag == 18  # COSE Sign1 tag
        assert len(cose_obj.value) == 4

    def test_payload_contains_pcrs(self):
        """Attestation payload should contain PCR values."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation()

        cose_obj = cbor2.loads(doc)
        payload = cbor2.loads(cose_obj.value[2])
        assert "pcrs" in payload
        assert 0 in payload["pcrs"]
        assert 1 in payload["pcrs"]
        assert 2 in payload["pcrs"]

    def test_payload_contains_nonce_when_provided(self):
        """Nonce should be embedded in the attestation payload."""
        stub = NSMStub(eif_path="test.eif")
        nonce = b"fresh-nonce-12345"
        doc = stub.get_attestation(nonce=nonce)

        cose_obj = cbor2.loads(doc)
        payload = cbor2.loads(cose_obj.value[2])
        assert payload["nonce"] == nonce

    def test_payload_contains_public_key_when_provided(self):
        """Public key should be embedded in the attestation payload."""
        stub = NSMStub(eif_path="test.eif")
        pubkey = b"\x04" + b"\x00" * 96  # Fake uncompressed P-384 point
        doc = stub.get_attestation(public_key=pubkey)

        cose_obj = cbor2.loads(doc)
        payload = cbor2.loads(cose_obj.value[2])
        assert payload["public_key"] == pubkey

    def test_payload_has_timestamp(self):
        """Attestation should contain a recent timestamp."""
        import time

        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation()

        cose_obj = cbor2.loads(doc)
        payload = cbor2.loads(cose_obj.value[2])
        ts_ms = payload["timestamp"]
        assert isinstance(ts_ms, int)
        # Should be within last 5 seconds
        assert abs(ts_ms / 1000 - time.time()) < 5

    def test_payload_has_cabundle(self):
        """Attestation should contain a certificate bundle."""
        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation()

        cose_obj = cbor2.loads(doc)
        payload = cbor2.loads(cose_obj.value[2])
        assert "cabundle" in payload
        assert len(payload["cabundle"]) >= 1
        assert isinstance(payload["cabundle"][0], bytes)

    def test_signature_is_valid(self):
        """The COSE Sign1 signature should verify with the stub's signing key."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        stub = NSMStub(eif_path="test.eif")
        doc = stub.get_attestation(nonce=b"test")

        cose_obj = cbor2.loads(doc)
        protected, _, payload_bytes, signature = cose_obj.value

        # Reconstruct Sig_structure
        sig_structure = cbor2.dumps(["Signature1", protected, b"", payload_bytes])

        # Verify with the stub's public key
        stub.signing_key.public_key().verify(
            signature, sig_structure, ec.ECDSA(hashes.SHA384())
        )

    def test_deterministic_pcrs_for_same_eif(self):
        """Same eif_path should produce same PCR values."""
        stub_a = NSMStub(eif_path="image.eif")
        stub_b = NSMStub(eif_path="image.eif")
        assert stub_a.pcrs == stub_b.pcrs

    def test_different_pcrs_for_different_eif(self):
        """Different eif_path should produce different PCR values."""
        stub_a = NSMStub(eif_path="image-a.eif")
        stub_b = NSMStub(eif_path="image-b.eif")
        assert stub_a.pcrs[0] != stub_b.pcrs[0]
