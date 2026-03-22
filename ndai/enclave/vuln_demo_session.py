"""Combined verification + negotiation + sealed delivery session for the demo.

Orchestrates the complete 0day marketplace lifecycle:
1. Build target environment (TargetSpec → Docker)
2. Verify PoC via capability oracles
3. Negotiate price via AI agents (Nash bargaining)
4. Seal exploit for buyer (ECIES re-encryption)

Each phase emits progress events via the callback for SSE streaming.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from ndai.enclave.agents.base_agent import VulnerabilitySubmission
from ndai.enclave.negotiation.shelf_life import VulnNegotiationResult
from ndai.enclave.vuln_session import VulnNegotiationSession, VulnSessionConfig
from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    TargetSpec,
    VerificationResult,
)
from ndai.enclave.vuln_verify.oracles import OracleManager
from ndai.enclave.vuln_verify.poc_executor import PoCExecutor
from ndai.enclave.vuln_verify.protocol import VulnVerificationProtocol
from ndai.enclave.vuln_verify.sealed_delivery import SealedDelivery, SealedDeliveryProtocol

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class DemoSessionResult:
    """Complete result of the demo pipeline."""
    verification: VerificationResult | None = None
    negotiation: VulnNegotiationResult | None = None
    sealed_delivery: SealedDelivery | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.negotiation is not None and self.error is None


@dataclass
class DemoSessionConfig:
    """Configuration for the combined demo session."""
    target_spec: TargetSpec
    vulnerability: VulnerabilitySubmission
    budget_cap: float
    buyer_public_key_der: bytes | None = None
    exploit_plaintext: bytes | None = None
    overlay: BuyerOverlay | None = None
    llm_provider: str = "openai"
    api_key: str = ""
    llm_model: str = "gpt-4o"
    software_category: str = "default"
    skip_verification: bool = False
    skip_sealed_delivery: bool = False


class VulnDemoSession:
    """Full demo pipeline: verify → negotiate → seal.

    Usage:
        config = DemoSessionConfig(
            target_spec=xz_target_spec,
            vulnerability=xz_vuln_submission,
            budget_cap=2.5,
        )
        session = VulnDemoSession(config, progress_callback=my_callback)
        result = session.run()
    """

    def __init__(
        self,
        config: DemoSessionConfig,
        progress_callback: ProgressCallback | None = None,
        executor: PoCExecutor | None = None,
        oracle: OracleManager | None = None,
    ):
        self.config = config
        self._progress = progress_callback
        self._executor = executor
        self._oracle = oracle

    def run(self) -> DemoSessionResult:
        """Execute the complete demo pipeline."""
        result = DemoSessionResult()

        try:
            # Phase 1: Verification
            if not self.config.skip_verification:
                self._emit("phase_start", {"phase": "verification", "description": "Verifying exploit via capability oracles"})
                result.verification = self._run_verification()
                self._emit("phase_complete", {
                    "phase": "verification",
                    "claimed": result.verification.unpatched_capability.claimed.value,
                    "verified": result.verification.unpatched_capability.verified_level.value if result.verification.unpatched_capability.verified_level else None,
                    "reliability": result.verification.unpatched_capability.reliability_score,
                })

                if result.verification.unpatched_capability.verified_level is None:
                    result.error = "PoC verification failed — no capability verified"
                    self._emit("pipeline_error", {"error": result.error})
                    return result

            # Phase 2: Negotiation
            self._emit("phase_start", {"phase": "negotiation", "description": "AI agents negotiating price via Nash bargaining"})
            result.negotiation = self._run_negotiation()
            self._emit("phase_complete", {
                "phase": "negotiation",
                "outcome": result.negotiation.outcome.value,
                "final_price": result.negotiation.final_price,
                "rounds": result.negotiation.negotiation_rounds,
            })

            if result.negotiation.outcome.value != "agreement":
                result.error = f"Negotiation ended: {result.negotiation.reason}"
                self._emit("pipeline_error", {"error": result.error})
                return result

            # Phase 3: Sealed delivery
            if not self.config.skip_sealed_delivery and self.config.exploit_plaintext and self.config.buyer_public_key_der:
                self._emit("phase_start", {"phase": "sealed_delivery", "description": "Sealing exploit for buyer delivery"})
                result.sealed_delivery = self._run_sealed_delivery()
                self._emit("phase_complete", {
                    "phase": "sealed_delivery",
                    "delivery_hash": result.sealed_delivery.delivery_hash[:16] + "...",
                    "key_commitment": result.sealed_delivery.key_commitment[:16] + "...",
                })

            self._emit("pipeline_complete", {
                "verification_passed": result.verification is not None,
                "deal_reached": result.negotiation.outcome.value == "agreement",
                "delivery_sealed": result.sealed_delivery is not None,
            })

        except Exception as exc:
            result.error = str(exc)
            logger.exception("Demo pipeline error: %s", exc)
            self._emit("pipeline_error", {"error": str(exc)})

        return result

    def _run_verification(self) -> VerificationResult:
        """Run capability-oracle verification."""
        executor = self._executor or PoCExecutor(enforce_rlimits=False)
        oracle = self._oracle or OracleManager()

        protocol = VulnVerificationProtocol(
            spec=self.config.target_spec,
            overlay=self.config.overlay,
            executor=executor,
            oracle=oracle,
        )

        self._emit("verification_step", {"step": "starting_services"})
        result = protocol.run()
        return result

    def _run_negotiation(self) -> VulnNegotiationResult:
        """Run AI-powered Nash bargaining negotiation."""
        session_config = VulnSessionConfig(
            vulnerability=self.config.vulnerability,
            budget_cap=self.config.budget_cap,
            llm_provider=self.config.llm_provider,
            api_key=self.config.api_key,
            llm_model=self.config.llm_model,
            software_category=self.config.software_category,
        )

        def negotiation_progress(phase: str, data: dict):
            self._emit("negotiation_step", {"step": phase, **data})

        session = VulnNegotiationSession(session_config, progress_callback=negotiation_progress)
        return session.run()

    def _run_sealed_delivery(self) -> SealedDelivery:
        """Seal exploit for buyer delivery."""
        protocol = SealedDeliveryProtocol()
        return protocol.seal(
            exploit_plaintext=self.config.exploit_plaintext,
            buyer_public_key_der=self.config.buyer_public_key_der,
        )

    def _emit(self, event: str, data: dict):
        if self._progress:
            try:
                self._progress(event, data)
            except Exception:
                logger.warning("Progress callback failed for event=%s", event)
