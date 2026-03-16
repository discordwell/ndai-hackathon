"""Simulated NSM device for local development and testing.

Generates self-signed COSE Sign1 attestation documents using a test key.
The attestation documents have the same structure as real Nitro NSM output
but are signed with a locally-generated key (no security guarantees).

This keeps the existing test suite passing while allowing the enclave code
to use a uniform NSM interface regardless of environment.
"""

import hashlib
import logging
import time
from typing import Any

import cbor2
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


class NSMStub:
    """Simulated NSM that generates self-signed COSE Sign1 attestation docs.

    For local development only — provides no security guarantees.
    The certificate chain contains a single self-signed cert (no real AWS root).

    Usage:
        stub = NSMStub(eif_path="test.eif")
        attestation_doc = stub.get_attestation(
            public_key=ephemeral_pubkey_der,
            nonce=os.urandom(32),
        )
    """

    def __init__(self, eif_path: str = "test.eif"):
        self._eif_path = eif_path
        # Generate a test signing key (P-384 to match Nitro's curve)
        self._signing_key = ec.generate_private_key(ec.SECP384R1())
        self._cert = self._make_self_signed_cert()
        self._cert_der = self._cert.public_bytes(serialization.Encoding.DER)
        # Deterministic PCRs based on eif_path (matching SimulatedTEEProvider)
        self._pcrs = {
            0: hashlib.sha384(f"pcr0:{eif_path}".encode()).digest(),
            1: hashlib.sha384(f"pcr1:{eif_path}".encode()).digest(),
            2: hashlib.sha384(f"pcr2:{eif_path}".encode()).digest(),
        }

    def _make_self_signed_cert(self) -> x509.Certificate:
        """Generate a self-signed X.509 certificate for test attestation signing."""
        import datetime

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "NDAI Test NSM"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NDAI Test"),
        ])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self._signing_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(self._signing_key, hashes.SHA384())
        )
        return cert

    def get_attestation(
        self,
        public_key: bytes | None = None,
        user_data: bytes | None = None,
        nonce: bytes | None = None,
    ) -> bytes:
        """Generate a simulated COSE Sign1 attestation document.

        The document structure matches real Nitro attestation:
        - CBOR Tag 18 (COSE Sign1): [protected, unprotected, payload, signature]
        - Payload is a CBOR map with: pcrs, public_key, nonce, user_data,
          timestamp, cabundle, module_id, digest

        Args:
            public_key: DER-encoded public key to embed in attestation.
            user_data: Optional user data.
            nonce: Optional nonce for freshness.

        Returns:
            CBOR-encoded COSE Sign1 attestation document.
        """
        # Build payload map (matches Nitro attestation structure)
        payload_map: dict[str, Any] = {
            "module_id": f"ndai-test-{self._eif_path}",
            "digest": "SHA384",
            "timestamp": int(time.time() * 1000),  # milliseconds since epoch
            "pcrs": self._pcrs,
            "cabundle": [self._cert_der],  # Single self-signed cert
        }
        if public_key is not None:
            payload_map["public_key"] = public_key
        if user_data is not None:
            payload_map["user_data"] = user_data
        if nonce is not None:
            payload_map["nonce"] = nonce

        payload_bytes = cbor2.dumps(payload_map)

        # Build COSE Sign1 structure
        # Protected header: algorithm = ES384 (-35)
        protected = cbor2.dumps({1: -35})  # 1 = alg, -35 = ES384

        # Unprotected header: empty
        unprotected = {}

        # Sign: Sig_structure = ["Signature1", protected, b"", payload]
        sig_structure = cbor2.dumps(["Signature1", protected, b"", payload_bytes])
        signature = self._signing_key.sign(sig_structure, ec.ECDSA(hashes.SHA384()))

        # COSE Sign1 = Tag(18, [protected, unprotected, payload, signature])
        cose_array = [protected, unprotected, payload_bytes, signature]
        attestation_doc = cbor2.dumps(cbor2.CBORTag(18, cose_array))

        logger.debug(
            "NSMStub generated attestation: %d bytes (nonce=%s, pubkey=%s)",
            len(attestation_doc),
            len(nonce) if nonce else None,
            len(public_key) if public_key else None,
        )

        return attestation_doc

    @property
    def signing_key(self) -> ec.EllipticCurvePrivateKey:
        """Expose the signing key for test verification."""
        return self._signing_key

    @property
    def cert_der(self) -> bytes:
        """The DER-encoded self-signed certificate."""
        return self._cert_der

    @property
    def pcrs(self) -> dict[int, bytes]:
        """The deterministic PCR values for this stub."""
        return dict(self._pcrs)
