"""Attestation verification for TEE providers.

Nitro attestation documents are CBOR-encoded COSE Sign1 structures.
This module provides:
- AttestationResult: parsed attestation data with optional enclave public key
- verify_attestation: validates Nitro attestation documents with full COSE
  signature verification and certificate chain validation to AWS root CA
- SimulatedAttestationVerifier: validates the JSON attestation from SimulatedTEEProvider
"""

import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Maximum age of an attestation document before it's considered stale
ATTESTATION_MAX_AGE_SEC = 300  # 5 minutes


@dataclass(frozen=True)
class AttestationResult:
    """Parsed and validated attestation document."""

    valid: bool
    pcrs: dict[int, str]  # PCR index -> hex digest
    enclave_cid: int | None
    timestamp: float | None
    enclave_public_key: bytes | None = None  # DER-encoded public key from attestation
    error: str | None = None


def verify_attestation(
    attestation_doc: bytes,
    expected_pcrs: dict[int, str] | None = None,
    nonce: bytes | None = None,
    max_age_sec: float = ATTESTATION_MAX_AGE_SEC,
    skip_signature_check: bool = False,
) -> AttestationResult:
    """Verify a Nitro attestation document.

    Full verification includes:
    1. Parse COSE Sign1 structure
    2. Extract and verify certificate chain to AWS Nitro root CA
    3. Verify ECDSA signature with leaf certificate
    4. Validate PCR values against expected
    5. Validate nonce for freshness
    6. Check timestamp is recent (within max_age_sec)
    7. Extract enclave public key if present

    Args:
        attestation_doc: Raw attestation bytes. For Nitro, this is CBOR-encoded
            COSE Sign1. For simulated, this is JSON.
        expected_pcrs: Optional dict of PCR index -> expected hex digest.
            If provided, all specified PCRs must match.
        nonce: Optional nonce that must appear in the attestation document.
        max_age_sec: Maximum allowed age of the attestation in seconds.
        skip_signature_check: If True, skip COSE signature and cert chain
            verification. Used for testing with self-signed stubs.

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
    return _verify_nitro_cbor(
        attestation_doc, expected_pcrs, nonce, max_age_sec, skip_signature_check
    )


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
    max_age_sec: float,
    skip_signature_check: bool,
) -> AttestationResult:
    """Verify a Nitro attestation document (CBOR COSE Sign1 format).

    Full verification: COSE Sign1 signature check, certificate chain validation
    to AWS Nitro root CA, PCR matching, nonce check, timestamp freshness.

    The Nitro attestation document structure (COSE Sign1):
        Tag(18, [protected, unprotected, payload, signature])
    where payload is a CBOR map containing:
        - pcrs: map of PCR index -> bytes
        - nonce: optional bytes
        - timestamp: uint (milliseconds since epoch)
        - cabundle: array of X.509 DER certificates
        - public_key: optional bytes (enclave's ephemeral public key)
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

        protected_bytes = cose_array[0]
        payload_bytes = cose_array[2]
        signature = cose_array[3]

        # Decode payload
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

        # Extract enclave public key (DER bytes)
        enclave_public_key = payload.get("public_key")
        if enclave_public_key is not None and not isinstance(enclave_public_key, bytes):
            enclave_public_key = None

        # --- COSE signature and certificate chain verification ---
        if not skip_signature_check:
            sig_result = _verify_cose_signature(
                protected_bytes, payload_bytes, signature, payload
            )
            if sig_result is not None:
                return AttestationResult(
                    valid=False,
                    pcrs=pcrs,
                    enclave_cid=None,
                    timestamp=timestamp,
                    enclave_public_key=enclave_public_key,
                    error=sig_result,
                )

        # --- Nonce validation ---
        if nonce is not None:
            doc_nonce = payload.get("nonce")
            if doc_nonce is None:
                return AttestationResult(
                    valid=False,
                    pcrs=pcrs,
                    enclave_cid=None,
                    timestamp=timestamp,
                    enclave_public_key=enclave_public_key,
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
                        enclave_public_key=enclave_public_key,
                        error="Nonce mismatch",
                    )
            elif isinstance(doc_nonce, str):
                if doc_nonce != nonce.hex():
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        enclave_public_key=enclave_public_key,
                        error="Nonce mismatch",
                    )

        # --- Timestamp freshness check ---
        if timestamp is not None and max_age_sec > 0:
            age = time.time() - timestamp
            if age > max_age_sec:
                return AttestationResult(
                    valid=False,
                    pcrs=pcrs,
                    enclave_cid=None,
                    timestamp=timestamp,
                    enclave_public_key=enclave_public_key,
                    error=f"Attestation too old: {age:.0f}s (max {max_age_sec}s)",
                )
            if age < -60:  # Allow 60s clock skew
                return AttestationResult(
                    valid=False,
                    pcrs=pcrs,
                    enclave_cid=None,
                    timestamp=timestamp,
                    enclave_public_key=enclave_public_key,
                    error=f"Attestation timestamp is {-age:.0f}s in the future",
                )

        # --- PCR validation ---
        if expected_pcrs:
            for idx, expected_hex in expected_pcrs.items():
                actual = pcrs.get(idx)
                if actual is None:
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        enclave_public_key=enclave_public_key,
                        error=f"PCR{idx} not present in attestation document",
                    )
                if actual.lower() != expected_hex.lower():
                    return AttestationResult(
                        valid=False,
                        pcrs=pcrs,
                        enclave_cid=None,
                        timestamp=timestamp,
                        enclave_public_key=enclave_public_key,
                        error=(
                            f"PCR{idx} mismatch: expected {expected_hex[:16]}..., "
                            f"got {actual[:16]}..."
                        ),
                    )

        logger.info("Nitro attestation verified successfully")
        return AttestationResult(
            valid=True,
            pcrs=pcrs,
            enclave_cid=None,
            timestamp=timestamp,
            enclave_public_key=enclave_public_key,
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


def _verify_cose_signature(
    protected_bytes: bytes,
    payload_bytes: bytes,
    signature: bytes,
    payload: dict,
) -> str | None:
    """Verify COSE Sign1 signature and certificate chain.

    Returns:
        None if verification succeeds, error string if it fails.
    """
    import cbor2
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives import hashes

    from ndai.tee.nitro_root_cert import get_root_certificate

    # --- Extract and validate certificate chain ---
    cabundle = payload.get("cabundle")
    if not cabundle or not isinstance(cabundle, list):
        return "Missing or invalid cabundle in attestation"

    # Parse all certificates in the chain
    certs: list[x509.Certificate] = []
    for i, cert_der in enumerate(cabundle):
        if not isinstance(cert_der, bytes):
            return f"cabundle[{i}] is not bytes"
        try:
            cert = x509.load_der_x509_certificate(cert_der)
            certs.append(cert)
        except Exception as exc:
            return f"Failed to parse cabundle[{i}]: {exc}"

    if len(certs) < 1:
        return "cabundle is empty"

    # The chain order in Nitro attestation is: [root, intermediate..., leaf]
    # Leaf cert's public key is used to verify the COSE signature.
    leaf_cert = certs[-1]
    root_cert = get_root_certificate()

    # Verify chain: each cert is signed by the next (or root for the first)
    chain_error = _verify_cert_chain(certs, root_cert)
    if chain_error is not None:
        return chain_error

    # --- Verify COSE Sign1 signature ---
    # Sig_structure = ["Signature1", protected, external_aad, payload]
    if isinstance(payload_bytes, dict):
        payload_for_sig = cbor2.dumps(payload_bytes)
    else:
        payload_for_sig = payload_bytes

    sig_structure = cbor2.dumps(["Signature1", protected_bytes, b"", payload_for_sig])

    leaf_public_key = leaf_cert.public_key()
    if not isinstance(leaf_public_key, ec.EllipticCurvePublicKey):
        return f"Leaf certificate has non-EC key: {type(leaf_public_key).__name__}"

    try:
        leaf_public_key.verify(signature, sig_structure, ec.ECDSA(hashes.SHA384()))
    except InvalidSignature:
        return "COSE Sign1 signature verification failed"
    except Exception as exc:
        return f"Signature verification error: {exc}"

    logger.debug("COSE Sign1 signature verified against leaf certificate")
    return None


def _verify_cert_chain(
    chain: list,
    root_cert,
) -> str | None:
    """Verify a certificate chain against the root CA.

    The chain order is [root_or_first, ..., leaf]. The first cert in the
    chain must be signed by the root CA, and each subsequent cert must
    be signed by the previous one.

    Returns:
        None if valid, error string otherwise.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
    from cryptography.hazmat.primitives import hashes

    # Verify first cert is signed by the root
    issuer_cert = root_cert
    for i, cert in enumerate(chain):
        issuer_key = issuer_cert.public_key()
        try:
            if isinstance(issuer_key, ec.EllipticCurvePublicKey):
                issuer_key.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    ec.ECDSA(cert.signature_hash_algorithm),
                )
            elif isinstance(issuer_key, rsa.RSAPublicKey):
                issuer_key.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    cert.signature_hash_algorithm,
                )
            else:
                return f"Unsupported key type in chain at position {i}: {type(issuer_key)}"
        except InvalidSignature:
            return f"Certificate chain verification failed at position {i}"
        except Exception as exc:
            return f"Certificate chain error at position {i}: {exc}"

        issuer_cert = cert

    return None


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
