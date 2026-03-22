"""Dstack TEE provider.

Uses the dstack SDK (Intel TDX Confidential VMs) as the TEE backend.
The app runs as a standard Docker container inside a dstack CVM.
Attestation uses TDX quotes, keys are derived via the dstack KMS.

Unlike Nitro (which uses vsock and runs enclave logic in a separate process),
dstack runs everything in-process inside the CVM. The "enclave" is the entire
container — all memory is hardware-encrypted and attestable.

Communication is in-process (like SimulatedTEEProvider) because the app
IS the enclave in dstack's model.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from typing import Any

from ndai.tee.provider import (
    EnclaveConfig,
    EnclaveIdentity,
    EnclaveNotFoundError,
    TEEProvider,
    TEEType,
)

logger = logging.getLogger(__name__)


def _is_dstack_available() -> bool:
    """Check if we're running inside a dstack CVM."""
    try:
        import os
        return os.path.exists("/var/run/dstack.sock")
    except Exception:
        return False


class DstackProvider(TEEProvider):
    """TEE provider using dstack (Intel TDX Confidential VMs).

    In dstack, the entire container runs inside a CVM with hardware-encrypted
    memory. There is no separate "enclave process" — the app itself is the
    enclave. Communication is in-process via async queues (same as simulated),
    but attestation uses real TDX quotes via the dstack SDK.
    """

    def __init__(self):
        self._enclaves: dict[str, _DstackEnclave] = {}
        self._dstack_available = _is_dstack_available()
        if self._dstack_available:
            logger.info("dstack CVM detected — using TDX attestation")
        else:
            logger.warning("dstack socket not found — attestation will use fallback")

    async def launch_enclave(self, config: EnclaveConfig) -> EnclaveIdentity:
        enclave_id = f"dstack-{uuid.uuid4().hex[:16]}"

        # In dstack, PCR-equivalent values come from the TDX quote's RTMR fields
        if self._dstack_available:
            pcrs = await self._get_rtmrs()
        else:
            seed = b"dstack-fallback"
            pcrs = {
                "pcr0": hashlib.sha384(b"rtmr0:" + seed).hexdigest(),
                "pcr1": hashlib.sha384(b"rtmr1:" + seed).hexdigest(),
                "pcr2": hashlib.sha384(b"rtmr2:" + seed).hexdigest(),
            }

        identity = EnclaveIdentity(
            enclave_id=enclave_id,
            enclave_cid=0,  # not applicable for dstack
            pcr0=pcrs["pcr0"],
            pcr1=pcrs["pcr1"],
            pcr2=pcrs["pcr2"],
            tee_type=TEEType.DSTACK,
        )
        self._enclaves[enclave_id] = _DstackEnclave(identity, config)
        return identity

    async def terminate_enclave(self, enclave_id: str) -> None:
        enclave = self._enclaves.pop(enclave_id, None)
        if enclave:
            enclave.destroy()

    async def send_message(self, enclave_id: str, message: dict[str, Any]) -> None:
        enclave = self._get_enclave(enclave_id)
        await enclave.inbox.put(message)

    async def receive_message(self, enclave_id: str) -> dict[str, Any]:
        enclave = self._get_enclave(enclave_id)
        return await enclave.outbox.get()

    async def get_attestation(self, enclave_id: str, nonce: bytes | None = None) -> bytes:
        """Get attestation using TDX quote via dstack SDK."""
        if self._dstack_available:
            return await self._get_tdx_attestation(enclave_id, nonce)
        else:
            # Fallback for development without dstack
            enclave = self._get_enclave(enclave_id)
            doc = {
                "type": "dstack_attestation_fallback",
                "enclave_id": enclave_id,
                "pcr0": enclave.identity.pcr0,
                "pcr1": enclave.identity.pcr1,
                "pcr2": enclave.identity.pcr2,
                "nonce": nonce.hex() if nonce else None,
                "warning": "DSTACK FALLBACK - not running in CVM",
            }
            return json.dumps(doc).encode()

    def get_tee_type(self) -> TEEType:
        return TEEType.DSTACK

    def get_enclave_queues(
        self, enclave_id: str
    ) -> tuple[asyncio.Queue[dict[str, Any]], asyncio.Queue[dict[str, Any]]]:
        """Get direct access to enclave queues (for in-process enclave logic)."""
        enclave = self._get_enclave(enclave_id)
        return enclave.inbox, enclave.outbox

    # --- dstack SDK integration ---

    async def _get_tdx_attestation(self, enclave_id: str, nonce: bytes | None) -> bytes:
        """Get a real TDX attestation quote via the dstack SDK."""
        try:
            from dstack_sdk import AsyncDstackClient

            client = AsyncDstackClient()
            report_data = nonce or b"\x00" * 64
            # Pad/truncate to 64 bytes as required by TDX
            report_data = report_data[:64].ljust(64, b"\x00")
            quote_response = await client.get_quote(report_data)

            enclave = self._get_enclave(enclave_id)
            doc = {
                "type": "dstack_tdx_attestation",
                "enclave_id": enclave_id,
                "pcr0": enclave.identity.pcr0,
                "pcr1": enclave.identity.pcr1,
                "pcr2": enclave.identity.pcr2,
                "nonce": nonce.hex() if nonce else None,
                "tdx_quote": quote_response.quote,
            }
            return json.dumps(doc).encode()
        except Exception as exc:
            logger.error("TDX attestation failed: %s", exc)
            raise

    async def _get_rtmrs(self) -> dict[str, str]:
        """Get RTMR values (TDX equivalent of PCRs) from the dstack SDK."""
        try:
            from dstack_sdk import AsyncDstackClient

            client = AsyncDstackClient()
            info = await client.info()
            tcb = info.tcb_info if hasattr(info, "tcb_info") else {}
            return {
                "pcr0": tcb.get("rtmr0", hashlib.sha384(b"dstack-rtmr0").hexdigest()),
                "pcr1": tcb.get("rtmr1", hashlib.sha384(b"dstack-rtmr1").hexdigest()),
                "pcr2": tcb.get("rtmr2", hashlib.sha384(b"dstack-rtmr2").hexdigest()),
            }
        except Exception:
            logger.warning("Failed to get RTMRs, using fallback values")
            return {
                "pcr0": hashlib.sha384(b"dstack-rtmr0").hexdigest(),
                "pcr1": hashlib.sha384(b"dstack-rtmr1").hexdigest(),
                "pcr2": hashlib.sha384(b"dstack-rtmr2").hexdigest(),
            }

    async def derive_key(self, path: str) -> str:
        """Derive a deterministic key from the dstack KMS.

        Returns the hex-encoded private key. The key is deterministic —
        same path always produces the same key for the same app.
        """
        try:
            from dstack_sdk import AsyncDstackClient

            client = AsyncDstackClient()
            key_response = await client.get_key(path)
            return key_response.key
        except Exception as exc:
            logger.error("dstack key derivation failed: %s", exc)
            raise

    def _get_enclave(self, enclave_id: str) -> "_DstackEnclave":
        enclave = self._enclaves.get(enclave_id)
        if not enclave:
            raise EnclaveNotFoundError(f"No enclave with ID {enclave_id}")
        if enclave.destroyed:
            raise EnclaveNotFoundError(f"Enclave {enclave_id} has been destroyed")
        return enclave


class _DstackEnclave:
    """In-process enclave within a dstack CVM."""

    def __init__(self, identity: EnclaveIdentity, config: EnclaveConfig):
        self.identity = identity
        self.config = config
        self.inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.destroyed = False

    def destroy(self):
        self.destroyed = True
        while not self.inbox.empty():
            try:
                self.inbox.get_nowait()
            except asyncio.QueueEmpty:
                break
        while not self.outbox.empty():
            try:
                self.outbox.get_nowait()
            except asyncio.QueueEmpty:
                break
