"""Attestation verification for TEE providers.

Nitro attestation documents are CBOR-encoded COSE Sign1 structures.
This module provides:
- AttestationResult: parsed attestation data
- verify_attestation: validates Nitro attestation documents (MVP: PCR + nonce checks)
- SimulatedAttestationVerifier: validates the JSON attestation from SimulatedTEEProvider

TODO(production): Full certificate chain validation against the AWS Nitro root
certificate. Requires cbor2 and cryptography packages for COSE Sign1 parsing
and X.509 chain verification.
"""

import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttestationResult:
    """Parsed and validated attestation document."""

    valid: bool
    pcrs: dict[int, str]  # PCR index -> hex digest
    enclave_cid: int | None
    timestamp: float | None
    error: str | None = None


def verify_attestation(
    attestation_doc: bytes,
    expected_pcrs: dict[int, str] | None = None,
    nonce: bytes | None = None,
) -> AttestationResult:
    """Verify a Nitro attestation document.

    For MVP: parse the document structure and validate PCR values.
    Full crypto verification requires the AWS Nitro root certificate chain.

    Args:
        attestation_doc: Raw attestation bytes. For Nitro, this is CBOR-encoded
            COSE Sign1. For simulated, this is JSON.
        expected_pcrs: Optional dict of PCR index -> expected hex digest.
            If provided, all specified PCRs must match.
        nonce: Optional nonce that must appear in the attestation document.

    Returns:
        AttestationResult with validity status and extracted PCR values.
    """
    # Try simulated format first (JSON), then Nitro (CBOR)
    try:
        doc = json.loads(attestation_doc)
        if doc.get("type") == "simulated_attestation":
            return _verify_simulated(doc, expected_pcrs, nonce)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    # Nitro CBOR format
    return _verify_nitro_cbor(attestation_doc, expected_pcrs, nonce)


def _verify_simulated(
    doc: dict,
    expected_pcrs: dict[int, str] | None,
    nonce: bytes | None,
) -> AttestationResult:
    """Verify a simulated attestation document (JSON format)."""
    verifier = SimulatedAttestationVerifier()
    return verifier.verify(doc, expected_pcrs, nonce)


def _verify_nitro_cbor(
    raw: bytes,
    expected_pcrs: dict[int, str] | None,
    nonce: bytes | None,
) -> AttestationResult:
    """Verify a Nitro attestation document (CBOR COSE Sign1 format).

    MVP implementation: attempts to parse the CBOR structure and extract PCRs.
    Full certificate chain validation is deferred to production.

    The Nitro attestation document structure (COSE Sign1):
        Tag(18, [protected, unprotected, payload, signature])
    where payload is a CBOR map containing:
        - pcrs: map of PCR index -> bytes
        - nonce: optional bytes
        - timestamp: uint (milliseconds since epoch)
        - cabundle: array of X.509 certificates
        - public_key: optional bytes
    """
    try:
        import cbor2
    except ImportError:
        logger.warning(
            "cbor2 not installed; cannot parse Nitro attestation. "
            "Install with: pip install cbor2"
        )
        return AttestationResult(
            valid=False,
            pcrs={},
            enclave_cid=None,
            timestamp=None,
            error="cbor2 package not installed — cannot parse Nitro attestation",
        )

    try:
        # COSE Sign1 is CBOR Tag 18 wrapping [protected, unprotected, payload, signature]
        cose_obj = cbor2.loads(raw)

        # Handle tagged or untagged COSE Sign1
        if hasattr(cose_obj, "value"):
            # CBORTag object
            cose_array = cose_obj.value
        elif isinstance(cose_obj, list):
            cose_array = cose_obj
        else:
            return AttestationResult(
                valid=False,
                pcrs={},
                enclave_cid=None,
                timestamp=None,
                error=f"Unexpected COSE structure type: {type(cose_obj).__name__}",
            )

        if len(cose_array) < 4:
            return AttestationResult(
                valid=False,
                pcrs={},
                enclave_cid=None,
                timestamp=None,
                error=f"COSE Sign1 requires 4 elements, got {len(cose_array)}",
            )

        # Payload is the third element, itself a CBOR-encoded map
        payload_bytes = cose_array[2]
        if isinstance(payload_bytes, bytes):
            payload = cbor2.loads(payload_bytes)
        elif isinstance(payload_bytes, dict):
            payload = payload_bytes
        else:
            return AttestationResult(
                valid=False,
                pcrs={},
                enclave_cid=None,
                timestamp=None,
                error=f"Unexpected payload type: {type(payload_bytes).__name__}",
            )

        # Extract PCRs
        raw_pcrs = payload.get("pcrs", {})
        pcrs: dict[int, str] = {}
        for idx, value in raw_pcrs.items():
            if isinstance(value, bytes):
                pcrs[int(idx)] = value.hex()
            elif isinstance(value, str):
                pcrs[int(idx)] = value
            else:
                pcrs[int(idx)] = str(value)

        # Extract timestamp
        timestamp_ms = payload.get("timestamp")
        timestamp = float(timestamp_ms) / 1000.0 if timestamp_ms is not None else None

        # Validate nonce
        if nonce is not None:
            doc_nonce = payload.get("nonce")
            if doc_nonce is None:
                return AttestationResult(
                    valid=False,
                    pcrs=pcrs,
                    enclave_cid=None,
                    timestamp=timestamp,
                    error="Nonce expected but not present in attestation document",
                )
            # Nonce may be bytes or hex string
            if isinstance(doc_nonce, bytes):
                if doc_nonce != nonce:
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        error="Nonce mismatch",
                    )
            elif isinstance(doc_nonce, str):
                if doc_nonce != nonce.hex():
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        error="Nonce mismatch",
                    )

        # Validate PCRs against expected values
        if expected_pcrs:
            for idx, expected_hex in expected_pcrs.items():
                actual = pcrs.get(idx)
                if actual is None:
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        error=f"PCR{idx} not present in attestation document",
                    )
                if actual.lower() != expected_hex.lower():
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        error=(
                            f"PCR{idx} mismatch: expected {expected_hex[:16]}..., "
                            f"got {actual[:16]}..."
                        ),
                    )

        # TODO(production): Verify COSE Sign1 signature against cabundle.
        # TODO(production): Validate cabundle chains to AWS Nitro root cert.
        logger.warning(
            "Nitro attestation PCR check passed, but COSE signature and "
            "certificate chain verification are NOT yet implemented."
        )

        return AttestationResult(
            valid=True,
            pcrs=pcrs,
            enclave_cid=None,  # Not directly in attestation doc; caller has it
            timestamp=timestamp,
        )

    except Exception as exc:
        logger.error("Failed to parse Nitro attestation: %s", exc)
        return AttestationResult(
            valid=False,
            pcrs={},
            enclave_cid=None,
            timestamp=None,
            error=f"Failed to parse attestation: {exc}",
        )


class SimulatedAttestationVerifier:
    """Verifier for SimulatedTEEProvider's JSON attestation format.

    The simulated attestation is a JSON object with:
        - type: "simulated_attestation"
        - enclave_id: str
        - pcr0, pcr1, pcr2: hex digests (SHA-384)
        - nonce: hex string or None
        - warning: str
    """

    def verify(
        self,
        doc: dict,
        expected_pcrs: dict[int, str] | None = None,
        nonce: bytes | None = None,
    ) -> AttestationResult:
        """Verify a simulated attestation document.

        Args:
            doc: Parsed JSON attestation document.
            expected_pcrs: Optional PCR values to check against.
            nonce: Optional nonce to validate.

        Returns:
            AttestationResult with validity status.
        """
        if doc.get("type") != "simulated_attestation":
            return AttestationResult(
                valid=False,
                pcrs={},
                enclave_cid=None,
                timestamp=None,
                error=f"Not a simulated attestation: type={doc.get('type')}",
            )

        # Extract PCRs from flat fields
        pcrs: dict[int, str] = {}
        for i in range(3):
            key = f"pcr{i}"
            if key in doc:
                pcrs[i] = doc[key]

        timestamp = time.time()

        # Validate nonce
        if nonce is not None:
            doc_nonce = doc.get("nonce")
            if doc_nonce is None:
                return AttestationResult(
                    valid=False,
                    pcrs=pcrs,
                    enclave_cid=None,
                    timestamp=timestamp,
                    error="Nonce expected but not present in attestation",
                )
            if doc_nonce != nonce.hex():
                return AttestationResult(
                    valid=False,
                    pcrs=pcrs,
                    enclave_cid=None,
                    timestamp=timestamp,
                    error=f"Nonce mismatch: expected {nonce.hex()}, got {doc_nonce}",
                )

        # Validate PCRs against expected values
        if expected_pcrs:
            for idx, expected_hex in expected_pcrs.items():
                actual = pcrs.get(idx)
                if actual is None:
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        error=f"PCR{idx} not present in attestation",
                    )
                if actual.lower() != expected_hex.lower():
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        error=(
                            f"PCR{idx} mismatch: expected {expected_hex[:16]}..., "
                            f"got {actual[:16]}..."
                        ),
                    )

        logger.debug(
            "Simulated attestation verified (WARNING: no security guarantees)"
        )
        return AttestationResult(
            valid=True,
            pcrs=pcrs,
            enclave_cid=None,
            timestamp=timestamp,
        )
