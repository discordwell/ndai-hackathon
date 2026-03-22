"""Verification protocol — orchestrates capability-oracle-based PoC testing.

Sequence:
1. Start target services
2. Plant capability oracles (canary files, callback listener)
3. Run PoC N times against UNPATCHED target → check oracles → reliability score
4. If buyer overlay: apply → re-plant oracles → re-run PoC → check oracles
5. Build VerificationResult with CapabilityResult for unpatched + patched

The seller says "my exploit achieves ACE." The enclave independently verifies
by planting a canary that only code execution could retrieve. The seller's PoC
must output the canary value to prove the claim.
"""

import logging
from datetime import datetime, timezone

from ndai.enclave.verification import SessionVerificationChain
from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    CapabilityLevel,
    CapabilityResult,
    PoCResult,
    TargetSpec,
    VerificationResult,
)
from ndai.enclave.vuln_verify.oracles import OracleManager
from ndai.enclave.vuln_verify.overlay_handler import OverlayHandler
from ndai.enclave.vuln_verify.poc_executor import PoCExecutor

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Error during verification protocol."""


class VulnVerificationProtocol:
    """Runs the complete capability-oracle verification protocol."""

    def __init__(
        self,
        spec: TargetSpec,
        overlay: BuyerOverlay | None = None,
        overlay_handler: OverlayHandler | None = None,
        executor: PoCExecutor | None = None,
        oracle: OracleManager | None = None,
    ):
        self._spec = spec
        self._overlay = overlay
        self._overlay_handler = overlay_handler
        self._executor = executor or PoCExecutor()
        self._oracle = oracle or OracleManager()
        self._chain = SessionVerificationChain()

    def run(self) -> VerificationResult:
        """Execute full capability-oracle verification protocol."""
        claimed = self._spec.claimed_capability
        runs = max(1, claimed.reliability_runs)

        self._chain.record(
            "session_start",
            {
                "spec_id": self._spec.spec_id,
                "claimed_capability": claimed.level.value,
                "reliability_runs": runs,
            },
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
            logger.warning("Unhealthy services: %s — proceeding anyway", [s.name for s in unhealthy])

        # Phase 2: Plant oracles + run PoC (unpatched), with reliability
        logger.info("Phase 2: Running PoC against unpatched target (%d runs)", runs)
        unpatched_cap = self._run_with_oracles(claimed.level, runs, "unpatched")

        self._chain.record(
            "poc_unpatched",
            {
                "claimed": claimed.level.value,
                "verified": unpatched_cap.verified_level.value if unpatched_cap.verified_level else None,
                "reliability": unpatched_cap.reliability_score,
                "ace": unpatched_cap.ace_canary_found,
                "lpe": unpatched_cap.lpe_canary_found,
                "info": unpatched_cap.info_canary_found,
                "callback": unpatched_cap.callback_received,
                "crash": unpatched_cap.crash_detected,
            },
            f"Unpatched: verified={unpatched_cap.verified_level} reliability={unpatched_cap.reliability_score:.0%}",
        )

        # Phase 3: Apply overlay and re-test (if provided)
        patched_cap = None
        overlap_detected = None

        if self._overlay and self._overlay_handler:
            logger.info("Phase 3: Applying buyer overlay and re-testing")

            self._executor.stop_services(self._spec.services)
            self._overlay_handler.apply_overlay(self._overlay, self._spec.services)
            self._chain.record(
                "overlay_applied",
                {"file_count": len(self._overlay.file_replacements)},
                f"Applied {len(self._overlay.file_replacements)} file replacements",
            )

            # Restart services with patched binaries
            self._executor.start_services(self._spec.services)

            patched_cap = self._run_with_oracles(claimed.level, runs, "patched")

            self._chain.record(
                "poc_patched",
                {
                    "verified": patched_cap.verified_level.value if patched_cap.verified_level else None,
                    "reliability": patched_cap.reliability_score,
                },
                f"Patched: verified={patched_cap.verified_level} reliability={patched_cap.reliability_score:.0%}",
            )

            # Overlap: does the exploit survive the buyer's patches?
            unpatched_works = unpatched_cap.verified_level is not None
            patched_works = patched_cap.verified_level is not None
            overlap_detected = unpatched_works and patched_works

            logger.info("Overlap detected: %s", overlap_detected)

        # Phase 4: Finalize
        self._chain.record(
            "result_produced",
            {
                "unpatched_verified": unpatched_cap.verified_level.value if unpatched_cap.verified_level else None,
                "overlap": overlap_detected,
            },
            "Verification complete",
        )
        report = self._chain.finalize()

        self._executor.stop_services(self._spec.services)
        self._oracle.cleanup()

        return VerificationResult(
            spec_id=self._spec.spec_id,
            unpatched_capability=unpatched_cap,
            patched_capability=patched_cap,
            overlap_detected=overlap_detected,
            verification_chain_hash=report.final_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _run_with_oracles(
        self, claimed: CapabilityLevel, runs: int, phase: str
    ) -> CapabilityResult:
        """Plant oracles, run PoC N times, aggregate results.

        Between runs, services are restarted to randomize heap layout
        and ASLR base addresses — simulating real-world conditions.
        """
        successes = 0
        best_result: CapabilityResult | None = None

        for i in range(runs):
            # Fresh oracles each run (new canary values)
            self._oracle.cleanup()
            self._oracle.plant_oracles(claimed, self._spec.service_user)

            if i > 0:
                # Restart services between runs to randomize memory layout
                self._executor.stop_services(self._spec.services)
                self._executor.start_services(self._spec.services)

            logger.info("%s run %d/%d", phase, i + 1, runs)
            poc_result = self._executor.execute_poc(self._spec.poc)
            cap_result = self._oracle.check_result(poc_result, claimed)

            if cap_result.verified_level is not None:
                successes += 1

            # Keep the result with the highest verified level
            if best_result is None or _cap_rank(cap_result) > _cap_rank(best_result):
                best_result = cap_result

        if best_result is None:
            # Should never happen (runs >= 1)
            best_result = CapabilityResult(claimed=claimed, verified_level=None)

        # Return best result with reliability score
        score = successes / runs if runs > 0 else 0.0
        return CapabilityResult(
            claimed=best_result.claimed,
            verified_level=best_result.verified_level,
            ace_canary_found=best_result.ace_canary_found,
            lpe_canary_found=best_result.lpe_canary_found,
            info_canary_found=best_result.info_canary_found,
            callback_received=best_result.callback_received,
            crash_detected=best_result.crash_detected,
            dos_detected=best_result.dos_detected,
            reliability_score=round(score, 2),
            reliability_runs=runs,
        )


# Capability ranking for comparison
_CAP_RANKS = {
    None: 0,
    CapabilityLevel.CRASH: 1,
    CapabilityLevel.DOS: 2,
    CapabilityLevel.INFO_LEAK: 3,
    CapabilityLevel.ACE: 4,
    CapabilityLevel.CALLBACK: 5,
    CapabilityLevel.LPE: 6,
}


def _cap_rank(result: CapabilityResult) -> int:
    return _CAP_RANKS.get(result.verified_level, 0)
