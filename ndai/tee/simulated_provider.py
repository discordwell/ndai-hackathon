"""Simulated TEE provider for local development.

WARNING: This provides ZERO security guarantees. It exists solely to enable
local development without Nitro hardware. All data lives in process memory
with no isolation. Security tests MUST use NitroEnclaveProvider.
"""

import asyncio
import hashlib
import json
import uuid
from typing import Any

from ndai.tee.provider import (
    EnclaveConfig,
    EnclaveIdentity,
    EnclaveNotFoundError,
    TEEProvider,
    TEEType,
)


class _SimulatedEnclave:
    """In-memory enclave simulation."""

    def __init__(self, identity: EnclaveIdentity, config: EnclaveConfig):
        self.identity = identity
        self.config = config
        self.inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.destroyed = False

    def destroy(self):
        self.destroyed = True
        # Best-effort memory clearing
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


class SimulatedTEEProvider(TEEProvider):
    """Development TEE provider using in-memory queues.

    Behavior differences from production:
    - Attestation documents are self-signed with deterministic test values
    - PCR values are deterministic hashes of the config
    - Communication uses in-memory async queues instead of vsock
    - No memory isolation
    """

    def __init__(self):
        self._enclaves: dict[str, _SimulatedEnclave] = {}

    async def launch_enclave(self, config: EnclaveConfig) -> EnclaveIdentity:
        enclave_id = f"sim-{uuid.uuid4().hex[:16]}"
        cid = config.enclave_cid or (4 + len(self._enclaves))

        seed = (config.eif_path or "simulated").encode()
        identity = EnclaveIdentity(
            enclave_id=enclave_id,
            enclave_cid=cid,
            pcr0=hashlib.sha384(b"pcr0:" + seed).hexdigest(),
            pcr1=hashlib.sha384(b"pcr1:" + seed).hexdigest(),
            pcr2=hashlib.sha384(b"pcr2:" + seed).hexdigest(),
            tee_type=TEEType.SIMULATED,
        )
        self._enclaves[enclave_id] = _SimulatedEnclave(identity, config)
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
        enclave = self._get_enclave(enclave_id)
        doc = {
            "type": "simulated_attestation",
            "enclave_id": enclave_id,
            "pcr0": enclave.identity.pcr0,
            "pcr1": enclave.identity.pcr1,
            "pcr2": enclave.identity.pcr2,
            "nonce": nonce.hex() if nonce else None,
            "warning": "SIMULATED - NO SECURITY GUARANTEES",
        }
        return json.dumps(doc).encode()

    def get_tee_type(self) -> TEEType:
        return TEEType.SIMULATED

    def get_enclave_queues(
        self, enclave_id: str
    ) -> tuple[asyncio.Queue[dict[str, Any]], asyncio.Queue[dict[str, Any]]]:
        """Get direct access to enclave queues (for simulated enclave logic)."""
        enclave = self._get_enclave(enclave_id)
        return enclave.inbox, enclave.outbox

    def _get_enclave(self, enclave_id: str) -> _SimulatedEnclave:
        enclave = self._enclaves.get(enclave_id)
        if not enclave:
            raise EnclaveNotFoundError(f"No enclave with ID {enclave_id}")
        if enclave.destroyed:
            raise EnclaveNotFoundError(f"Enclave {enclave_id} has been destroyed")
        return enclave
