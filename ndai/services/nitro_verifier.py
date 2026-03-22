"""Nitro Enclave verification backend for Linux targets (Chrome, Firefox, Ubuntu).

Reuses the existing EIFBuilder and capability oracle pipeline. The key difference
from direct seller-provided verification is that the TargetSpec comes from the
platform-maintained KnownTarget, and only the PoC is seller-provided.
"""

import hashlib
import logging
from typing import Any

from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    ClaimedCapability,
    ConfigFile,
    PinnedPackage,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)
from ndai.models.known_target import KnownTarget
from ndai.models.verification_proposal import VerificationProposal
from ndai.services.verification_dispatcher import VerificationOutcome

logger = logging.getLogger(__name__)


class NitroVerifier:
    """Verification backend for Linux targets running in AWS Nitro Enclaves."""

    def build_target_spec(
        self,
        target: KnownTarget,
        proposal: VerificationProposal,
    ) -> TargetSpec:
        """Construct a TargetSpec from KnownTarget (platform) + PoC (seller).

        The target environment is entirely platform-defined. The seller only
        provides the PoC script. This prevents sellers from rigging the environment.
        """
        # Parse packages from JSON
        packages = []
        if target.packages_json:
            for pkg in target.packages_json:
                packages.append(PinnedPackage(name=pkg["name"], version=pkg["version"]))

        # Parse config files from JSON
        config_files = []
        if target.config_files_json:
            for cf in target.config_files_json:
                config_files.append(ConfigFile(
                    path=cf["path"],
                    content=cf["content"],
                    mode=cf.get("mode", 0o644),
                ))

        # Parse services from JSON
        services = []
        if target.services_json:
            for svc in target.services_json:
                services.append(ServiceSpec(
                    name=svc["name"],
                    start_command=svc["start_command"],
                    health_check=svc["health_check"],
                    timeout_sec=svc.get("timeout_sec", 30),
                ))

        # Build steps
        build_steps = target.build_steps_json or []

        # PoC from seller
        poc = PoCSpec(
            script_type=proposal.poc_script_type,
            script_content=proposal.poc_script,
            timeout_sec=60,
            run_as_user="poc",
        )

        # Claimed capability from seller
        capability = ClaimedCapability(
            level=CapabilityLevel(proposal.claimed_capability),
            reliability_runs=proposal.reliability_runs,
        )

        # Deterministic spec ID
        spec_id = hashlib.sha256(
            f"{target.slug}:{target.current_version}:{proposal.id}".encode()
        ).hexdigest()[:16]

        return TargetSpec(
            spec_id=spec_id,
            base_image=target.base_image or "ubuntu:22.04",
            packages=packages,
            config_files=config_files,
            services=services,
            poc=poc,
            claimed_capability=capability,
            build_steps=build_steps,
            service_user=target.service_user or "www-data",
        )

    async def verify(
        self,
        proposal: VerificationProposal,
        target: KnownTarget,
        progress_callback: Any = None,
    ) -> VerificationOutcome:
        """Run verification using the Nitro Enclave pipeline.

        Steps:
        1. Construct TargetSpec from KnownTarget + seller PoC
        2. Build EIF (or use cached)
        3. Launch enclave, run capability oracles
        4. Return CapabilityResult
        """
        try:
            if progress_callback:
                await progress_callback("building", {"message": "Constructing target specification..."})

            target_spec = self.build_target_spec(target, proposal)

            if progress_callback:
                await progress_callback("building", {
                    "message": f"Building EIF for {target.display_name} {target.current_version}...",
                    "spec_id": target_spec.spec_id,
                })

            # Build EIF
            from ndai.enclave.vuln_verify.builder import EIFBuilder
            builder = EIFBuilder()
            manifest = await builder.build_eif(target_spec)

            if progress_callback:
                await progress_callback("verifying", {
                    "message": "Running capability oracles...",
                    "pcr0": manifest.pcr0[:16] if manifest.pcr0 else None,
                })

            # Run verification via the enclave pipeline
            # In simulated mode, this runs locally; in Nitro mode, this launches a real enclave
            from ndai.config import settings as app_settings
            from ndai.tee.vuln_verify_orchestrator import VerificationConfig, VulnVerifyOrchestrator

            # Get the appropriate TEE provider based on tee_mode
            if app_settings.tee_mode == "nitro":
                from ndai.tee.nitro_provider import NitroEnclaveProvider
                provider = NitroEnclaveProvider()
            else:
                from ndai.tee.simulated_provider import SimulatedTEEProvider
                provider = SimulatedTEEProvider()

            config = VerificationConfig(
                target_spec=target_spec,
                eif_path=manifest.eif_path,
                expected_pcrs={0: manifest.pcr0, 1: manifest.pcr1, 2: manifest.pcr2}
                if manifest.pcr0 != "simulated" else None,
                api_key=app_settings.openai_api_key or app_settings.anthropic_api_key,
            )
            orchestrator = VulnVerifyOrchestrator(provider=provider)
            outcome = await orchestrator.run_verification(config)

            if progress_callback:
                phase = "passed" if outcome.unpatched_matches else "failed"
                await progress_callback(phase, {
                    "message": f"Verification {'passed' if outcome.unpatched_matches else 'failed'}",
                    "pcr0": outcome.pcr0[:16] if outcome.pcr0 else None,
                })

            return VerificationOutcome(
                success=outcome.unpatched_matches,
                capability_result={
                    "overlap_detected": outcome.overlap_detected,
                    "verification_chain_hash": outcome.verification_chain_hash,
                },
                chain_hash=outcome.verification_chain_hash,
                pcr0=outcome.pcr0,
                status="passed" if outcome.unpatched_matches else "failed",
            )

        except Exception as e:
            logger.exception("Nitro verification failed for proposal %s", proposal.id)
            return VerificationOutcome(
                success=False,
                status="error",
                error=str(e),
            )
