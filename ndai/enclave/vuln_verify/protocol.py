"""Verification protocol — orchestrates the full PoC test inside the enclave.

Sequence:
1. Start target services
2. Run PoC against UNPATCHED target → capture result
3. If buyer overlay: stop → apply → restart → re-run PoC → capture
4. Build attestation-signed result (only booleans leave, not stdout/stderr)
"""

import logging
from datetime import datetime, timezone

from ndai.enclave.verification import SessionVerificationChain
from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    PoCResult,
    TargetSpec,
    VerificationResult,
)
from ndai.enclave.vuln_verify.overlay_handler import OverlayHandler
from ndai.enclave.vuln_verify.poc_executor import PoCExecutor

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Error during verification protocol."""


class VulnVerificationProtocol:
    """Runs the complete PoC verification protocol inside the enclave."""

    def __init__(
        self,
        spec: TargetSpec,
        overlay: BuyerOverlay | None = None,
        overlay_handler: OverlayHandler | None = None,
        executor: PoCExecutor | None = None,
    ):
        self._spec = spec
        self._overlay = overlay
        self._overlay_handler = overlay_handler
        self._executor = executor or PoCExecutor()
        self._chain = SessionVerificationChain()

    def run(self) -> VerificationResult:
        """Execute full verification protocol."""
        self._chain.record(
            "session_start",
            {"spec_id": self._spec.spec_id, "base_image": self._spec.base_image},
            "Verification session started",
        )

        # Phase 1: Start services
        logger.info("Phase 1: Starting target services")
        statuses = self._executor.start_services(self._spec.services)
        self._chain.record(
            "services_started",
            {"services": [s.name for s in statuses], "all_healthy": all(s.healthy for s in statuses)},
            f"Started {len(statuses)} services",
        )

        unhealthy = [s for s in statuses if not s.healthy]
        if unhealthy:
            names = [s.name for s in unhealthy]
            logger.warning("Unhealthy services: %s — proceeding anyway", names)

        # Phase 2: Run PoC (unpatched)
        logger.info("Phase 2: Running PoC against unpatched target")
        unpatched_result = self._executor.execute_poc(self._spec.poc)
        unpatched_matches = self._executor.check_outcome(
            unpatched_result, self._spec.expected_outcome
        )
        self._chain.record(
            "poc_unpatched",
            {
                "exit_code": unpatched_result.exit_code,
                "signal": unpatched_result.signal,
                "timed_out": unpatched_result.timed_out,
                "matches_expected": unpatched_matches,
            },
            f"Unpatched PoC: exit={unpatched_result.exit_code} signal={unpatched_result.signal} matches={unpatched_matches}",
        )
        logger.info(
            "Unpatched result: exit=%d signal=%s matches=%s",
            unpatched_result.exit_code, unpatched_result.signal, unpatched_matches,
        )

        # Phase 3: Apply overlay and re-test (if provided)
        patched_result = None
        patched_matches = None
        overlap_detected = None

        if self._overlay and self._overlay_handler:
            logger.info("Phase 3: Applying buyer overlay and re-testing")

            # Apply overlay (stops/restarts services internally)
            self._overlay_handler.apply_overlay(self._overlay, self._spec.services)
            self._chain.record(
                "overlay_applied",
                {"file_count": len(self._overlay.file_replacements)},
                f"Applied {len(self._overlay.file_replacements)} file replacements",
            )

            # Re-run PoC against patched target
            patched_result = self._executor.execute_poc(self._spec.poc)
            patched_matches = self._executor.check_outcome(
                patched_result, self._spec.expected_outcome
            )
            self._chain.record(
                "poc_patched",
                {
                    "exit_code": patched_result.exit_code,
                    "signal": patched_result.signal,
                    "timed_out": patched_result.timed_out,
                    "matches_expected": patched_matches,
                },
                f"Patched PoC: exit={patched_result.exit_code} signal={patched_result.signal} matches={patched_matches}",
            )

            # Overlap detection:
            # If PoC works on unpatched AND also works on patched → the 0day
            # survives the buyer's patches → overlap (buyer already has similar fix coverage)
            # If PoC works on unpatched but NOT on patched → buyer's patches block it
            overlap_detected = unpatched_matches and patched_matches

            logger.info(
                "Patched result: exit=%d signal=%s matches=%s overlap=%s",
                patched_result.exit_code, patched_result.signal,
                patched_matches, overlap_detected,
            )

        # Phase 4: Finalize
        self._chain.record(
            "result_produced",
            {"unpatched_matches": unpatched_matches, "overlap_detected": overlap_detected},
            "Verification complete",
        )
        report = self._chain.finalize()

        # Stop services
        self._executor.stop_services(self._spec.services)

        return VerificationResult(
            spec_id=self._spec.spec_id,
            unpatched_result=unpatched_result,
            unpatched_matches_expected=unpatched_matches,
            patched_result=patched_result,
            patched_matches_expected=patched_matches,
            overlap_detected=overlap_detected,
            verification_chain_hash=report.final_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
