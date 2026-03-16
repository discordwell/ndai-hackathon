"""AWS Nitro Enclave TEE provider.

Production implementation using nitro-cli and AF_VSOCK for communication.
Must run on a Nitro-capable EC2 instance.
"""

import asyncio
import json
import socket
import struct
from typing import Any

from ndai.tee.provider import (
    EnclaveConfig,
    EnclaveIdentity,
    EnclaveLaunchError,
    EnclaveNotFoundError,
    TEEProvider,
    TEEType,
)

# AF_VSOCK constant (available on Linux)
AF_VSOCK = 40


class NitroEnclaveProvider(TEEProvider):
    """Production TEE provider using AWS Nitro Enclaves.

    Wraps nitro-cli for lifecycle management and AF_VSOCK sockets
    for communication. Requires a Nitro-capable EC2 instance.
    """

    def __init__(self):
        self._active_enclaves: dict[str, EnclaveIdentity] = {}

    async def launch_enclave(self, config: EnclaveConfig) -> EnclaveIdentity:
        cmd = [
            "nitro-cli", "run-enclave",
            "--cpu-count", str(config.cpu_count),
            "--memory", str(config.memory_mib),
            "--eif-path", config.eif_path,
        ]
        if config.enclave_cid is not None:
            cmd += ["--enclave-cid", str(config.enclave_cid)]
        if config.debug_mode:
            cmd.append("--debug-mode")

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise EnclaveLaunchError(f"nitro-cli failed: {stderr.decode()}")

        result = json.loads(stdout.decode())
        identity = EnclaveIdentity(
            enclave_id=result["EnclaveID"],
            enclave_cid=result["EnclaveCID"],
            pcr0="",  # Populated during attestation
            pcr1="",
            pcr2="",
            tee_type=TEEType.NITRO,
        )
        self._active_enclaves[identity.enclave_id] = identity
        return identity

    async def terminate_enclave(self, enclave_id: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "nitro-cli", "terminate-enclave", "--enclave-id", enclave_id,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        self._active_enclaves.pop(enclave_id, None)

    async def send_message(self, enclave_id: str, message: dict[str, Any]) -> None:
        identity = self._get_identity(enclave_id)
        data = json.dumps(message).encode()
        await self._vsock_send(identity.enclave_cid, identity.enclave_cid, data)

    async def receive_message(self, enclave_id: str) -> dict[str, Any]:
        identity = self._get_identity(enclave_id)
        data = await self._vsock_receive(identity.enclave_cid, 5000)
        return json.loads(data)

    async def get_attestation(self, enclave_id: str, nonce: bytes | None = None) -> bytes:
        request = {
            "action": "get_attestation",
            "nonce": nonce.hex() if nonce else None,
        }
        await self.send_message(enclave_id, request)
        response = await self.receive_message(enclave_id)
        return json.dumps(response).encode()

    def get_tee_type(self) -> TEEType:
        return TEEType.NITRO

    def _get_identity(self, enclave_id: str) -> EnclaveIdentity:
        identity = self._active_enclaves.get(enclave_id)
        if not identity:
            raise EnclaveNotFoundError(f"No active enclave: {enclave_id}")
        return identity

    @staticmethod
    async def _vsock_send(cid: int, port: int, data: bytes) -> None:
        """Send length-prefixed data over vsock."""
        loop = asyncio.get_event_loop()
        sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        try:
            await loop.run_in_executor(None, sock.connect, (cid, port))
            frame = struct.pack(">I", len(data)) + data
            await loop.run_in_executor(None, sock.sendall, frame)
        finally:
            sock.close()

    @staticmethod
    async def _vsock_receive(cid: int, port: int) -> bytes:
        """Receive length-prefixed data over vsock."""
        loop = asyncio.get_event_loop()
        sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        try:
            await loop.run_in_executor(None, sock.connect, (cid, port))
            length_bytes = await loop.run_in_executor(None, sock.recv, 4)
            length = struct.unpack(">I", length_bytes)[0]
            data = b""
            while len(data) < length:
                chunk = await loop.run_in_executor(None, sock.recv, length - len(data))
                if not chunk:
                    raise ConnectionError("vsock closed prematurely")
                data += chunk
            return data
        finally:
            sock.close()
