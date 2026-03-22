"""Parent-side orchestrator for PoC verification in custom EIF enclaves.

Manages the full lifecycle:
1. Launch enclave with per-target EIF
2. Attest (verify PCRs match the per-target build)
3. Deliver API key
4. Send vuln_verify action with TargetSpec
5. Optionally deliver encrypted buyer overlay
6. Receive signed verification result
7. Terminate enclave
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass

from ndai.config import Settings
from ndai.config import settings as default_settings
from ndai.enclave.vuln_verify.models import TargetSpec, VerificationResult
from ndai.tee.attestation import verify_attestation
from ndai.tee.provider import EnclaveConfig, EnclaveIdentity, TEEError, TEEProvider, TEEType

logger = logging.getLogger(__name__)


class VerificationOrchestrationError(TEEError):
    """Error during verification orchestration."""


@dataclass
class VerificationConfig:
    """Everything needed to run a PoC verification in an enclave."""
    target_spec: TargetSpec
    eif_path: str = ""                              # Path to per-target EIF
    buyer_overlay_encrypted: bytes | None = None    # ECIES-encrypted overlay
    expected_pcrs: dict[int, str] | None = None
    api_key: str = ""
    enclave_config: EnclaveConfig | None = None


@dataclass
class VerificationOutcome:
    """Result from the verification orchestrator."""
    unpatched_matches: bool
    patched_matches: bool | None
    overlap_detected: bool | None
    verification_chain_hash: str
    pcr0: str
    timestamp: str


class VulnVerifyOrchestrator:
    """Orchestrates PoC verification lifecycle in a custom-built EIF."""

    def __init__(self, provider: TEEProvider, settings: Settings | None = None):
        self._provider = provider
        self._settings = settings or default_settings

    async def run_verification(
        self, config: VerificationConfig
    ) -> VerificationOutcome:
        """Run a full PoC verification lifecycle."""
        tee_type = self._provider.get_tee_type()
        logger.info("Starting verification orchestration (tee_type=%s)", tee_type.value)

        if tee_type == TEEType.SIMULATED:
            return await self._run_simulated(config)
        else:
            return await self._run_nitro(config)

    async def _run_simulated(self, config: VerificationConfig) -> VerificationOutcome:
        """Run verification in-process (simulated mode)."""
        enclave_config = config.enclave_config or self._default_enclave_config(config)
        identity: EnclaveIdentity | None = None
        start_time = time.monotonic()

        try:
            # Launch simulated enclave
            identity = await self._provider.launch_enclave(enclave_config)
            logger.info("Simulated enclave launched: %s", identity.enclave_id)

            # Verify attestation
            nonce = os.urandom(32)
            attestation_doc = await self._provider.get_attestation(
                identity.enclave_id, nonce=nonce
            )
            attestation = verify_attestation(
                attestation_doc,
                expected_pcrs=config.expected_pcrs,
                nonce=nonce,
            )
            logger.info("Attestation verified")

            # Run verification protocol in-process
            from ndai.enclave.vuln_verify.protocol import VulnVerificationProtocol
            from ndai.enclave.vuln_verify.overlay_handler import OverlayHandler

            overlay = None
            overlay_handler = None
            if config.buyer_overlay_encrypted:
                # In simulated mode, skip ECIES (no real keypair)
                # Just pass None overlay for now
                logger.warning("Buyer overlay not supported in simulated mode (no ECIES)")

            protocol = VulnVerificationProtocol(
                spec=config.target_spec,
                overlay=overlay,
                overlay_handler=overlay_handler,
            )

            timeout = self._settings.negotiation_timeout_sec
            result = await asyncio.wait_for(
                asyncio.to_thread(protocol.run),
                timeout=timeout,
            )

            elapsed = time.monotonic() - start_time
            unpatched_ok = result.unpatched_capability.verified_level is not None
            patched_ok = (
                result.patched_capability.verified_level is not None
                if result.patched_capability else None
            )
            logger.info(
                "Verification complete: unpatched=%s overlap=%s elapsed=%.1fs",
                unpatched_ok, result.overlap_detected, elapsed,
            )

            return VerificationOutcome(
                unpatched_matches=unpatched_ok,
                patched_matches=patched_ok,
                overlap_detected=result.overlap_detected,
                verification_chain_hash=result.verification_chain_hash,
                pcr0=attestation.pcrs.get(0, "simulated"),
                timestamp=result.timestamp,
            )

        except TimeoutError:
            elapsed = time.monotonic() - start_time
            logger.error("Verification timed out after %.1fs", elapsed)
            raise VerificationOrchestrationError(
                f"Verification timed out after {elapsed:.0f}s"
            )
        except TEEError:
            raise
        except Exception as exc:
            logger.error("Verification failed: %s", exc, exc_info=True)
            raise VerificationOrchestrationError(
                f"Verification failed: {exc}"
            ) from exc
        finally:
            if identity is not None:
                try:
                    await self._provider.terminate_enclave(identity.enclave_id)
                    logger.info("Enclave terminated: %s", identity.enclave_id)
                except Exception:
                    logger.warning("Failed to terminate enclave")

    async def _run_nitro(self, config: VerificationConfig) -> VerificationOutcome:
        """Run verification in a real Nitro Enclave."""
        enclave_config = config.enclave_config or self._default_enclave_config(config)
        identity: EnclaveIdentity | None = None

        try:
            # Step 1: Launch enclave with per-target EIF
            logger.info("Launching Nitro enclave with EIF: %s", enclave_config.eif_path)
            identity = await self._provider.launch_enclave(enclave_config)
            logger.info("Enclave launched: id=%s cid=%d", identity.enclave_id, identity.enclave_cid)

            # Step 2: Attest
            nonce = os.urandom(32)
            attestation_doc = await self._provider.get_attestation(
                identity.enclave_id, nonce=nonce
            )
            attestation = verify_attestation(
                attestation_doc,
                expected_pcrs=config.expected_pcrs,
                nonce=nonce,
            )
            logger.info("Attestation verified: pcr0=%s", attestation.pcrs.get(0, "?")[:16])

            # Step 3: Deliver API key (if needed for LLM-assisted analysis)
            if config.api_key:
                from ndai.enclave.ephemeral_keys import ecies_encrypt
                encrypted_key = ecies_encrypt(
                    attestation.enclave_public_key_der, config.api_key.encode()
                )
                await self._provider.send_message(identity.enclave_id, {
                    "action": "deliver_key",
                    "encrypted_key": list(encrypted_key),
                })
                key_resp = await self._provider.receive_message(identity.enclave_id)
                if key_resp.get("status") != "ok":
                    raise VerificationOrchestrationError("Key delivery failed")

            # Step 4: Deliver buyer overlay BEFORE verification (enclave reads
            # pending_overlay when vuln_verify runs, so it must already be present)
            if config.buyer_overlay_encrypted:
                import base64
                await self._provider.send_message(identity.enclave_id, {
                    "action": "deliver_overlay",
                    "encrypted_overlay": base64.b64encode(config.buyer_overlay_encrypted).decode(),
                })
                overlay_resp = await self._provider.receive_message(identity.enclave_id)
                if overlay_resp.get("status") != "ok":
                    raise VerificationOrchestrationError(
                        f"Overlay delivery failed: {overlay_resp.get('error', 'unknown')}"
                    )

            # Step 5: Send verification request (overlay already in enclave state)
            spec_dict = self._serialize_target_spec(config.target_spec)
            await self._provider.send_message(identity.enclave_id, {
                "action": "vuln_verify",
                "data": {"target_spec": spec_dict},
            })

            # Step 6: Receive verification result
            result_resp = await self._provider.receive_message(identity.enclave_id)
            if result_resp.get("status") != "ok":
                raise VerificationOrchestrationError(
                    f"Verification failed: {result_resp.get('error', 'unknown')}"
                )

            r = result_resp["result"]
            return VerificationOutcome(
                unpatched_matches=r["unpatched_matches"],
                patched_matches=r.get("patched_matches"),
                overlap_detected=r.get("overlap_detected"),
                verification_chain_hash=r["verification_chain_hash"],
                pcr0=identity.pcr0,
                timestamp=r["timestamp"],
            )

        except TEEError:
            raise
        except Exception as exc:
            logger.error("Nitro verification failed: %s", exc, exc_info=True)
            raise VerificationOrchestrationError(f"Nitro verification failed: {exc}") from exc
        finally:
            if identity is not None:
                try:
                    await self._provider.terminate_enclave(identity.enclave_id)
                except Exception:
                    logger.warning("Failed to terminate enclave")

    def _default_enclave_config(self, config: VerificationConfig) -> EnclaveConfig:
        return EnclaveConfig(
            cpu_count=self._settings.enclave_cpu_count,
            memory_mib=self._settings.vuln_verify_enclave_memory_mib
            if hasattr(self._settings, 'vuln_verify_enclave_memory_mib')
            else self._settings.enclave_memory_mib,
            eif_path=config.eif_path or self._settings.enclave_eif_path,
            vsock_port=self._settings.enclave_vsock_port,
            debug_mode=True,
        )

    def _serialize_target_spec(self, spec: TargetSpec) -> dict:
        """Serialize TargetSpec to dict for vsock transmission."""
        return {
            "spec_id": spec.spec_id,
            "base_image": spec.base_image,
            "packages": [{"name": p.name, "version": p.version} for p in spec.packages],
            "config_files": [{"path": c.path, "content": c.content, "mode": c.mode} for c in spec.config_files],
            "services": [
                {"name": s.name, "start_command": s.start_command,
                 "health_check": s.health_check, "timeout_sec": s.timeout_sec}
                for s in spec.services
            ],
            "poc": {
                "script_type": spec.poc.script_type,
                "script_content": spec.poc.script_content,
                "timeout_sec": spec.poc.timeout_sec,
                "run_as_user": spec.poc.run_as_user,
            },
            "claimed_capability": {
                "level": spec.claimed_capability.level.value,
                "reliability_runs": spec.claimed_capability.reliability_runs,
                "crash_signal": spec.claimed_capability.crash_signal,
                "exit_code": spec.claimed_capability.exit_code,
            },
            "service_user": spec.service_user,
        }
