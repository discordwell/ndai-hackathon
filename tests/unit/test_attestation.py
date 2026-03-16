"""Unit tests for attestation verification."""

import hashlib
import json

import pytest

from ndai.tee.attestation import (
    AttestationResult,
    SimulatedAttestationVerifier,
    verify_attestation,
)


def _make_simulated_doc(
    pcr0: str = "aabb",
    pcr1: str = "ccdd",
    pcr2: str = "eeff",
    nonce: str | None = None,
    enclave_id: str = "sim-test",
) -> bytes:
    """Build a simulated attestation document as bytes."""
    doc = {
        "type": "simulated_attestation",
        "enclave_id": enclave_id,
        "pcr0": pcr0,
        "pcr1": pcr1,
        "pcr2": pcr2,
        "nonce": nonce,
        "warning": "SIMULATED - NO SECURITY GUARANTEES",
    }
    return json.dumps(doc).encode()


class TestSimulatedAttestationVerifier:
    def test_valid_attestation(self):
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-abc",
            "pcr0": "aabbcc",
            "pcr1": "ddeeff",
            "pcr2": "112233",
            "nonce": None,
            "warning": "SIMULATED",
        }
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc)
        assert result.valid is True
        assert result.pcrs == {0: "aabbcc", 1: "ddeeff", 2: "112233"}
        assert result.error is None

    def test_wrong_type_field(self):
        doc = {"type": "something_else"}
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc)
        assert result.valid is False
        assert "Not a simulated attestation" in result.error

    def test_nonce_validation_pass(self):
        nonce = b"test-nonce"
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-abc",
            "pcr0": "aa",
            "pcr1": "bb",
            "pcr2": "cc",
            "nonce": nonce.hex(),
            "warning": "SIMULATED",
        }
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc, nonce=nonce)
        assert result.valid is True

    def test_nonce_validation_fail_mismatch(self):
        nonce = b"expected-nonce"
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-abc",
            "pcr0": "aa",
            "pcr1": "bb",
            "pcr2": "cc",
            "nonce": b"wrong-nonce".hex(),
            "warning": "SIMULATED",
        }
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc, nonce=nonce)
        assert result.valid is False
        assert "Nonce mismatch" in result.error

    def test_nonce_validation_fail_missing(self):
        nonce = b"expected"
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-abc",
            "pcr0": "aa",
            "pcr1": "bb",
            "pcr2": "cc",
            "nonce": None,
            "warning": "SIMULATED",
        }
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc, nonce=nonce)
        assert result.valid is False
        assert "not present" in result.error

    def test_pcr_validation_pass(self):
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-abc",
            "pcr0": "aabbcc",
            "pcr1": "ddeeff",
            "pcr2": "112233",
            "nonce": None,
            "warning": "SIMULATED",
        }
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc, expected_pcrs={0: "aabbcc", 2: "112233"})
        assert result.valid is True

    def test_pcr_validation_fail(self):
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-abc",
            "pcr0": "aabbcc",
            "pcr1": "ddeeff",
            "pcr2": "112233",
            "nonce": None,
            "warning": "SIMULATED",
        }
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc, expected_pcrs={0: "wrong_value"})
        assert result.valid is False
        assert "PCR0 mismatch" in result.error

    def test_pcr_case_insensitive(self):
        doc = {
            "type": "simulated_attestation",
            "enclave_id": "sim-abc",
            "pcr0": "AABBCC",
            "pcr1": "bb",
            "pcr2": "cc",
            "nonce": None,
            "warning": "SIMULATED",
        }
        verifier = SimulatedAttestationVerifier()
        result = verifier.verify(doc, expected_pcrs={0: "aabbcc"})
        assert result.valid is True


class TestVerifyAttestation:
    def test_simulated_autodetect(self):
        doc_bytes = _make_simulated_doc(pcr0="abc123")
        result = verify_attestation(doc_bytes)
        assert result.valid is True
        assert result.pcrs[0] == "abc123"

    def test_simulated_with_nonce(self):
        nonce = b"my-nonce"
        doc_bytes = _make_simulated_doc(nonce=nonce.hex())
        result = verify_attestation(doc_bytes, nonce=nonce)
        assert result.valid is True

    def test_simulated_pcr_check(self):
        seed = b"simulated"
        expected_pcr0 = hashlib.sha384(b"pcr0:" + seed).hexdigest()
        doc_bytes = _make_simulated_doc(pcr0=expected_pcr0)
        result = verify_attestation(doc_bytes, expected_pcrs={0: expected_pcr0})
        assert result.valid is True

    def test_simulated_pcr_mismatch(self):
        doc_bytes = _make_simulated_doc(pcr0="actual_value")
        result = verify_attestation(
            doc_bytes, expected_pcrs={0: "expected_value"}
        )
        assert result.valid is False
        assert "PCR0 mismatch" in result.error

    def test_non_json_non_cbor_returns_error(self):
        result = verify_attestation(b"\x00\x01garbage")
        assert result.valid is False
        assert result.error is not None

    def test_attestation_result_frozen(self):
        result = AttestationResult(
            valid=True, pcrs={}, enclave_cid=None, timestamp=None
        )
        with pytest.raises(AttributeError):
            result.valid = False  # type: ignore[misc]
