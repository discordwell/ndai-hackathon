"""AWS Nitro Enclave TEE provider.

Production implementation using nitro-cli and AF_VSOCK for communication.
Must run on a Nitro-capable EC2 instance.

The enclave app (ndai.enclave.app) uses a single-connection request-response
protocol: accept → read request → process → write response → close. This
provider must keep the vsock connection open across send_message/receive_message
to match that protocol.
"""

import asyncio
import json
import logging
import socket
import struct
from typing import Any

from ndai.tee.provider import (
    EnclaveConfig,
    EnclaveIdentity,
    EnclaveLaunchError,
    EnclaveNotFoundError,
    TEEError,
    TEEProvider,
    TEEType,
)

logger = logging.getLogger(__name__)

# AF_VSOCK constant (available on Linux)
AF_VSOCK = 40


class NitroEnclaveProvider(TEEProvider):
    """Production TEE provider using AWS Nitro Enclaves.

    Wraps nitro-cli for lifecycle management and AF_VSOCK sockets
    for communication. Requires a Nitro-capable EC2 instance.

    The enclave app uses a single-connection request-response protocol:
    each send_message opens a vsock connection and keeps it alive so the
    subsequent receive_message can read the response on the same connection.
    """

    def __init__(self):
        self._active_enclaves: dict[str, EnclaveIdentity] = {}
        self._enclave_configs: dict[str, EnclaveConfig] = {}
        # Persistent connection for the current request-response cycle.
        # send_message stores the socket; receive_message reads from it and closes it.
        self._connections: dict[str, socket.socket] = {}

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
        self._enclave_configs[identity.enclave_id] = config
        return identity

    async def terminate_enclave(self, enclave_id: str) -> None:
        # Close any lingering connection
        self._close_connection(enclave_id)

        proc = await asyncio.create_subprocess_exec(
            "nitro-cli", "terminate-enclave", "--enclave-id", enclave_id,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        self._active_enclaves.pop(enclave_id, None)
        self._enclave_configs.pop(enclave_id, None)

    async def send_message(self, enclave_id: str, message: dict[str, Any]) -> None:
        """Send a message to the enclave, keeping the connection open for the response.

        The enclave uses a single-connection protocol: it reads one request and
        writes one response on the same connection. We must keep the socket alive
        so that receive_message() can read the response.
        """
        identity = self._get_identity(enclave_id)
        config = self._enclave_configs[enclave_id]

        # Close any stale connection from a previous request-response cycle
        self._close_connection(enclave_id)

        loop = asyncio.get_event_loop()
        sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        sock.settimeout(300)  # 5 min timeout for negotiations

        try:
            await loop.run_in_executor(
                None, sock.connect, (identity.enclave_cid, config.vsock_port)
            )
            data = json.dumps(message).encode()
            frame = struct.pack(">I", len(data)) + data
            await loop.run_in_executor(None, sock.sendall, frame)
        except Exception:
            sock.close()
            raise

        # Store the open connection for receive_message
        self._connections[enclave_id] = sock
        logger.debug(
            "Sent message to enclave %s (cid=%d port=%d), connection held open",
            enclave_id, identity.enclave_cid, config.vsock_port,
        )

    async def receive_message(self, enclave_id: str) -> dict[str, Any]:
        """Read the response from the enclave on the connection opened by send_message.

        Closes the connection after reading.
        """
        sock = self._connections.pop(enclave_id, None)
        if sock is None:
            raise TEEError(
                f"No open connection for enclave {enclave_id}. "
                "send_message must be called before receive_message."
            )

        try:
            data = await self._recv_frame(sock)
            return json.loads(data)
        finally:
            sock.close()

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

    def _close_connection(self, enclave_id: str) -> None:
        """Close and discard any stored connection for this enclave."""
        sock = self._connections.pop(enclave_id, None)
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    @staticmethod
    async def _recv_frame(sock: socket.socket) -> bytes:
        """Read a length-prefixed frame from an open socket."""
        loop = asyncio.get_event_loop()

        # Read 4-byte length header
        length_bytes = b""
        while len(length_bytes) < 4:
            chunk = await loop.run_in_executor(
                None, sock.recv, 4 - len(length_bytes)
            )
            if not chunk:
                raise ConnectionError("vsock closed during length read")
            length_bytes += chunk

        length = struct.unpack(">I", length_bytes)[0]

        # Read payload
        data = b""
        while len(data) < length:
            chunk = await loop.run_in_executor(
                None, sock.recv, min(length - len(data), 65536)
            )
            if not chunk:
                raise ConnectionError("vsock closed during payload read")
            data += chunk

        return data
