"""Abstract TEE provider interface.

Defines the contract for TEE implementations. The system supports multiple
backends: NitroEnclaveProvider for production, SimulatedTEEProvider for development.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TEEType(Enum):
    NITRO = "aws_nitro"
    DSTACK = "dstack"
    SIMULATED = "simulated"


@dataclass(frozen=True)
class EnclaveConfig:
    """Configuration for launching an enclave."""

    cpu_count: int = 2
    memory_mib: int = 1600
    eif_path: str = ""
    enclave_cid: int | None = None
    vsock_port: int = 5000
    debug_mode: bool = False
    max_session_duration_sec: int = 3600


@dataclass
class EnclaveIdentity:
    """Identity of a running enclave."""

    enclave_id: str
    enclave_cid: int
    pcr0: str  # Hash of enclave image
    pcr1: str  # Hash of kernel
    pcr2: str  # Hash of application
    tee_type: TEEType
    launched_at: float = field(default_factory=time.time)


class TEEError(Exception):
    """Base exception for TEE operations."""


class EnclaveLaunchError(TEEError):
    """Failed to launch enclave."""


class EnclaveNotFoundError(TEEError):
    """Enclave not found."""


class TEEProvider(ABC):
    """Abstract interface for TEE provisioning and communication."""

    @abstractmethod
    async def launch_enclave(self, config: EnclaveConfig) -> EnclaveIdentity:
        """Provision and boot a new enclave."""
        ...

    @abstractmethod
    async def terminate_enclave(self, enclave_id: str) -> None:
        """Terminate an enclave and release resources. Destroys all enclave memory."""
        ...

    @abstractmethod
    async def send_message(self, enclave_id: str, message: dict[str, Any]) -> None:
        """Send a structured message to the enclave."""
        ...

    @abstractmethod
    async def receive_message(self, enclave_id: str) -> dict[str, Any]:
        """Receive a structured message from the enclave."""
        ...

    @abstractmethod
    async def get_attestation(self, enclave_id: str, nonce: bytes | None = None) -> bytes:
        """Request an attestation document from the enclave."""
        ...

    @abstractmethod
    def get_tee_type(self) -> TEEType:
        """Return the TEE implementation type."""
        ...
