"""Real Nitro Security Module (NSM) device interface.

Communicates with /dev/nsm via ioctl to request attestation documents.
Only works inside an actual AWS Nitro Enclave. For local development,
use nsm_stub.py instead.

The NSM device accepts CBOR-encoded requests and returns CBOR-encoded
responses. The attestation document is a COSE Sign1 structure signed
by the NSM's private key, chaining up to the AWS Nitro Attestation PKI.

Protocol:
    1. Open /dev/nsm
    2. Send ioctl with CBOR request containing:
       - public_key: DER-encoded ephemeral public key (embedded in attestation)
       - user_data: optional user-supplied data
       - nonce: optional nonce for freshness
    3. Receive CBOR response containing the COSE Sign1 attestation document
"""

import ctypes
import ctypes.util
import fcntl
import logging
import os
import struct
from typing import Any

import cbor2

logger = logging.getLogger(__name__)

# NSM ioctl constants
# The NSM device uses a custom ioctl command for attestation requests.
# Magic number 0x0A, command 0x00 (from AWS Nitro SDK)
NSM_IOCTL_MAGIC = 0x0A
NSM_CMD_ATTESTATION = 0x00
NSM_DEVICE_PATH = "/dev/nsm"

# ioctl request structure sizes
NSM_REQUEST_MAX_SIZE = 0x1000  # 4 KiB for request
NSM_RESPONSE_MAX_SIZE = 0x4000  # 16 KiB for response


class NSMError(Exception):
    """Error communicating with the Nitro Security Module."""


class NSMDevice:
    """Interface to the real /dev/nsm device inside a Nitro Enclave.

    Usage:
        nsm = NSMDevice()
        attestation_doc = nsm.get_attestation(
            public_key=ephemeral_pubkey_der,
            nonce=os.urandom(32),
        )
    """

    def __init__(self, device_path: str = NSM_DEVICE_PATH):
        self._device_path = device_path
        self._fd: int | None = None

    def open(self) -> None:
        """Open the NSM device."""
        if self._fd is not None:
            return
        try:
            self._fd = os.open(self._device_path, os.O_RDWR)
            logger.info("Opened NSM device: %s (fd=%d)", self._device_path, self._fd)
        except OSError as exc:
            raise NSMError(f"Failed to open NSM device {self._device_path}: {exc}") from exc

    def close(self) -> None:
        """Close the NSM device."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "NSMDevice":
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get_attestation(
        self,
        public_key: bytes | None = None,
        user_data: bytes | None = None,
        nonce: bytes | None = None,
    ) -> bytes:
        """Request an attestation document from the NSM.

        Args:
            public_key: DER-encoded public key to embed in the attestation.
                       Used for secure key delivery (enclave proves it owns
                       the corresponding private key).
            user_data: Arbitrary user data to include in the attestation.
            nonce: Random nonce for attestation freshness.

        Returns:
            Raw COSE Sign1 attestation document bytes.

        Raises:
            NSMError: If the NSM request fails.
        """
        if self._fd is None:
            self.open()

        # Build the CBOR request map
        request_map: dict[str, Any] = {}
        if public_key is not None:
            request_map["public_key"] = public_key
        if user_data is not None:
            request_map["user_data"] = user_data
        if nonce is not None:
            request_map["nonce"] = nonce

        # The NSM expects a CBOR array: [command, request_map]
        # Command "Attestation" is represented as {"Attestation": request_map}
        request_cbor = cbor2.dumps({"Attestation": request_map})

        logger.debug(
            "NSM attestation request: public_key=%s nonce=%s user_data=%s",
            len(public_key) if public_key else None,
            len(nonce) if nonce else None,
            len(user_data) if user_data else None,
        )

        response_cbor = self._ioctl_request(request_cbor)
        return self._parse_attestation_response(response_cbor)

    def _ioctl_request(self, request_cbor: bytes) -> bytes:
        """Send a CBOR request to the NSM device via ioctl.

        The NSM kernel driver expects struct nsm_message with two iovec fields:
            struct nsm_message {
                struct iovec request;   // {void *iov_base, size_t iov_len}
                struct iovec response;  // {void *iov_base, size_t iov_len}
            };

        On 64-bit: sizeof(struct iovec) = 16, sizeof(struct nsm_message) = 32.
        The ioctl command is _IOWR(0x0A, 0, struct nsm_message).

        Returns:
            Raw CBOR response bytes.
        """
        assert self._fd is not None

        req_len = len(request_cbor)
        if req_len > NSM_REQUEST_MAX_SIZE:
            raise NSMError(f"NSM request too large: {req_len} bytes (max {NSM_REQUEST_MAX_SIZE})")

        # Allocate request and response buffers as ctypes arrays
        req_buf = (ctypes.c_char * req_len)(*request_cbor)
        resp_buf = (ctypes.c_char * NSM_RESPONSE_MAX_SIZE)()

        # Build struct nsm_message: two iovecs (pointer + length each)
        # struct iovec { void *iov_base; size_t iov_len; };
        # On 64-bit: each field is 8 bytes → iovec is 16 bytes → nsm_message is 32 bytes
        class Iovec(ctypes.Structure):
            _fields_ = [("iov_base", ctypes.c_void_p), ("iov_len", ctypes.c_size_t)]

        class NsmMessage(ctypes.Structure):
            _fields_ = [("request", Iovec), ("response", Iovec)]

        msg = NsmMessage()
        msg.request.iov_base = ctypes.cast(req_buf, ctypes.c_void_p)
        msg.request.iov_len = req_len
        msg.response.iov_base = ctypes.cast(resp_buf, ctypes.c_void_p)
        msg.response.iov_len = NSM_RESPONSE_MAX_SIZE

        try:
            fcntl.ioctl(self._fd, self._ioctl_cmd(), msg)
        except OSError as exc:
            raise NSMError(f"NSM ioctl failed: {exc}") from exc

        # After ioctl, response.iov_len is updated to actual response size
        resp_len = msg.response.iov_len
        if resp_len == 0:
            raise NSMError("NSM returned empty response")
        if resp_len > NSM_RESPONSE_MAX_SIZE:
            raise NSMError(f"NSM response too large: {resp_len}")

        return bytes(resp_buf[:resp_len])

    @staticmethod
    def _ioctl_cmd() -> int:
        """Compute the ioctl command number for NSM.

        _IOWR(NSM_IOCTL_MAGIC, NSM_CMD_ATTESTATION, struct nsm_message)
        sizeof(struct nsm_message) = 32 on 64-bit (two iovecs)
        Linux ioctl encoding: direction(2) | size(14) | type(8) | nr(8)
        """
        direction = 3  # _IOC_READ | _IOC_WRITE
        size = 32  # sizeof(struct nsm_message) on 64-bit
        return (direction << 30) | (size << 16) | (NSM_IOCTL_MAGIC << 8) | NSM_CMD_ATTESTATION

    def _parse_attestation_response(self, response_cbor: bytes) -> bytes:
        """Parse the NSM response and extract the attestation document.

        The response is CBOR: {"Attestation": {"document": <bytes>}}
        On error: {"Error": "<error_code>"}
        """
        try:
            response = cbor2.loads(response_cbor)
        except Exception as exc:
            raise NSMError(f"Failed to parse NSM response CBOR: {exc}") from exc

        if "Error" in response:
            raise NSMError(f"NSM returned error: {response['Error']}")

        attestation = response.get("Attestation")
        if attestation is None:
            raise NSMError(f"Unexpected NSM response structure: {list(response.keys())}")

        document = attestation.get("document")
        if document is None:
            raise NSMError("NSM attestation response missing 'document' field")

        if not isinstance(document, bytes):
            raise NSMError(f"NSM attestation document is not bytes: {type(document)}")

        logger.info("NSM attestation document received: %d bytes", len(document))
        return document


def is_nsm_available() -> bool:
    """Check whether the NSM device is accessible (i.e., we're inside a Nitro Enclave)."""
    return os.path.exists(NSM_DEVICE_PATH)
