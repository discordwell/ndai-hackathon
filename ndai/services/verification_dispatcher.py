"""Verification dispatcher — routes proposals to the correct verification backend."""

import logging
from dataclasses import dataclass
from typing import Any

from ndai.models.known_target import KnownTarget
from ndai.models.verification_proposal import VerificationProposal

logger = logging.getLogger(__name__)


@dataclass
class VerificationOutcome:
    """Result returned by any verification backend."""
    success: bool
    capability_result: dict | None = None  # Serialized CapabilityResult
    chain_hash: str | None = None
    pcr0: str | None = None
    error: str | None = None
    status: str = "passed"  # "passed" | "failed" | "manual_review" | "error"


class VerificationDispatcher:
    """Routes proposals to the correct verification backend by target.verification_method."""

    def __init__(self) -> None:
        self._backends: dict[str, Any] = {}

    def register_backend(self, method: str, backend: Any) -> None:
        """Register a verification backend for a method."""
        self._backends[method] = backend

    async def dispatch(
        self,
        proposal: VerificationProposal,
        target: KnownTarget,
        progress_callback: Any = None,
    ) -> VerificationOutcome:
        """Dispatch a proposal to the correct backend."""
        method = target.verification_method
        logger.info(
            "Dispatching proposal %s to %s backend (target: %s %s)",
            proposal.id, method, target.slug, target.current_version,
        )

        if method == "nitro":
            return await self._verify_nitro(proposal, target, progress_callback)
        elif method == "ec2_windows":
            return await self._verify_windows(proposal, target, progress_callback)
        elif method == "corellium":
            return await self._verify_ios(proposal, target, progress_callback)
        elif method == "manual":
            return VerificationOutcome(
                success=False,
                status="manual_review",
                error="Manual review required — platform operator will verify.",
            )
        else:
            return VerificationOutcome(
                success=False,
                status="error",
                error=f"Unknown verification method: {method}",
            )

    async def _verify_nitro(
        self,
        proposal: VerificationProposal,
        target: KnownTarget,
        progress_callback: Any = None,
    ) -> VerificationOutcome:
        """Linux path — Nitro Enclave verification with pre-built EIF."""
        backend = self._backends.get("nitro")
        if not backend:
            from ndai.services.nitro_verifier import NitroVerifier
            backend = NitroVerifier()
            self._backends["nitro"] = backend
        return await backend.verify(proposal, target, progress_callback)

    async def _verify_windows(
        self,
        proposal: VerificationProposal,
        target: KnownTarget,
        progress_callback: Any = None,
    ) -> VerificationOutcome:
        """Windows path — EC2 VM verification."""
        backend = self._backends.get("ec2_windows")
        if not backend:
            from ndai.services.windows_verifier import WindowsVerifier
            backend = WindowsVerifier()
            self._backends["ec2_windows"] = backend
        return await backend.verify(proposal, target, progress_callback)

    async def _verify_ios(
        self,
        proposal: VerificationProposal,
        target: KnownTarget,
        progress_callback: Any = None,
    ) -> VerificationOutcome:
        """iOS path — Corellium (stub)."""
        backend = self._backends.get("corellium")
        if not backend:
            from ndai.services.ios_verifier import IOSVerifier
            backend = IOSVerifier()
            self._backends["corellium"] = backend
        return await backend.verify(proposal, target, progress_callback)
