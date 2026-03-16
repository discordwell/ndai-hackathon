"""Parent-side enclave orchestrator.

Manages the full lifecycle of a negotiation running inside a TEE:
1. Launch enclave via TEEProvider
2. Start vsock LLM proxy OR TCP tunnel (Nitro mode)
3. Verify attestation (with COSE signature verification in Nitro mode)
4. Encrypt and deliver API key to enclave (Nitro mode)
5. Send negotiation inputs to the enclave
6. Wait for the negotiation result
7. Terminate the enclave (always, even on error)

For SimulatedTEEProvider, the negotiation runs in-process via NegotiationSession
since there is no real enclave to communicate with.

Security model (Nitro mode):
- Attestation includes enclave's ephemeral public key (COSE-signed by NSM)
- Parent encrypts API key to enclave's public key (ECIES)
- LLM traffic goes through TCP tunnel (parent sees only TLS ciphertext)
- Parent never has access to invention data or decrypted API key
"""

import asyncio
import base64
import logging
import os
import time
from dataclasses import dataclass

from ndai.config import Settings
from ndai.config import settings as default_settings
from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    NegotiationResult,
    SecurityParams,
)
from ndai.enclave.session import NegotiationSession, SessionConfig
from ndai.tee.attestation import AttestationResult, verify_attestation
from ndai.tee.provider import (
    EnclaveConfig,
    EnclaveIdentity,
    TEEError,
    TEEProvider,
    TEEType,
)

logger = logging.getLogger(__name__)


class OrchestrationError(TEEError):
    """Error during enclave orchestration lifecycle."""


class AttestationError(OrchestrationError):
    """Attestation verification failed."""


@dataclass
class EnclaveNegotiationConfig:
    """Everything needed to run a negotiation in an enclave."""

    invention: InventionSubmission
    budget_cap: float
    security_params: SecurityParams
    max_rounds: int = 5
    llm_provider: str = "anthropic"  # "anthropic" or "openai"
    api_key: str = ""  # Stays on parent, never enters enclave in plaintext
    llm_model: str = "claude-sonnet-4-20250514"
    # Legacy aliases (kept for backwards compatibility)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    expected_pcrs: dict[int, str] | None = None  # For attestation verification
    enclave_config: EnclaveConfig | None = None  # Override defaults


class EnclaveOrchestrator:
    """Orchestrates negotiation lifecycle inside a TEE.

    Works with both NitroEnclaveProvider (production) and
    SimulatedTEEProvider (development). The simulated path runs
    NegotiationSession in-process; the Nitro path communicates
    with a real enclave over vsock.
    """

    def __init__(
        self,
        provider: TEEProvider,
        settings: Settings | None = None,
    ):
        self._provider = provider
        self._settings = settings or default_settings

    async def run_negotiation(
        self, config: EnclaveNegotiationConfig
    ) -> NegotiationResult:
        """Run a full negotiation lifecycle in an enclave.

        Steps:
            1. Launch enclave
            2. Start LLM proxy/tunnel
            3. Verify attestation (COSE signature + cert chain in Nitro mode)
            4. Deliver API key (encrypted to enclave's ephemeral public key)
            5. Send negotiation inputs
            6. Wait for result
            7. Terminate enclave

        Args:
            config: Full negotiation configuration including invention,
                security params, and optional enclave overrides.

        Returns:
            NegotiationResult from the enclave negotiation.

        Raises:
            OrchestrationError: If the lifecycle fails unrecoverably.
            AttestationError: If attestation verification fails.
        """
        tee_type = self._provider.get_tee_type()
        logger.info("Starting negotiation orchestration (tee_type=%s)", tee_type.value)

        if tee_type == TEEType.SIMULATED:
            return await self._run_simulated(config)
        else:
            return await self._run_nitro(config)

    async def _run_simulated(
        self, config: EnclaveNegotiationConfig
    ) -> NegotiationResult:
        """Run negotiation in-process using SimulatedTEEProvider.

        The simulated provider has no real enclave, so we launch/terminate
        for lifecycle testing but run NegotiationSession directly.
        """
        enclave_config = config.enclave_config or self._default_enclave_config()
        identity: EnclaveIdentity | None = None
        start_time = time.monotonic()

        try:
            # Step 1: Launch simulated enclave (for lifecycle completeness)
            logger.info("Launching simulated enclave")
            identity = await self._provider.launch_enclave(enclave_config)
            logger.info(
                "Simulated enclave launched: id=%s cid=%d",
                identity.enclave_id,
                identity.enclave_cid,
            )

            # Step 2: No vsock proxy needed for simulated mode

            # Step 3: Verify attestation (validates simulated attestation format)
            nonce = os.urandom(32)
            attestation_doc = await self._provider.get_attestation(
                identity.enclave_id, nonce=nonce
            )
            attestation = verify_attestation(
                attestation_doc,
                expected_pcrs=config.expected_pcrs,
                nonce=nonce,
            )
            self._check_attestation(attestation)
            logger.info(
                "Simulated attestation verified (pcrs=%s)",
                {k: v[:16] + "..." for k, v in attestation.pcrs.items()},
            )

            # Step 4+5: Run NegotiationSession directly in-process
            # Resolve API key: prefer generic field, fall back to legacy
            api_key = config.api_key or config.anthropic_api_key
            llm_model = config.llm_model
            if config.llm_model == "claude-sonnet-4-20250514" and config.anthropic_model != "claude-sonnet-4-20250514":
                llm_model = config.anthropic_model

            session_config = SessionConfig(
                invention=config.invention,
                budget_cap=config.budget_cap,
                security_params=config.security_params,
                max_rounds=config.max_rounds,
                llm_provider=config.llm_provider,
                api_key=api_key,
                llm_model=llm_model,
            )

            session = NegotiationSession(session_config)
            timeout = self._settings.negotiation_timeout_sec

            logger.info(
                "Running negotiation in-process (timeout=%ds)", timeout
            )
            result = await asyncio.wait_for(
                asyncio.to_thread(session.run),
                timeout=timeout,
            )

            elapsed = time.monotonic() - start_time
            logger.info(
                "Simulated negotiation complete: outcome=%s elapsed=%.1fs",
                result.outcome.value,
                elapsed,
            )
            return result

        except TimeoutError:
            elapsed = time.monotonic() - start_time
            logger.error(
                "Simulated negotiation timed out after %.1fs", elapsed
            )
            return NegotiationResult(
                outcome=NegotiationOutcomeType.ERROR,
                final_price=None,
                omega_hat=0.0,
                theta=0.0,
                phi=0.0,
                seller_payoff=None,
                buyer_payoff=None,
                reason=f"Negotiation timed out after {elapsed:.0f}s",
            )
        except AttestationError:
            raise
        except TEEError:
            raise
        except Exception as exc:
            logger.error("Simulated orchestration failed: %s", exc, exc_info=True)
            raise OrchestrationError(
                f"Simulated negotiation failed: {exc}"
            ) from exc
        finally:
            # Step 6: Always terminate
            if identity is not None:
                try:
                    await self._provider.terminate_enclave(identity.enclave_id)
                    logger.info(
                        "Simulated enclave terminated: %s", identity.enclave_id
                    )
                except Exception as term_exc:
                    logger.warning(
                        "Failed to terminate simulated enclave %s: %s",
                        identity.enclave_id,
                        term_exc,
                    )

    async def _run_nitro(
        self, config: EnclaveNegotiationConfig
    ) -> NegotiationResult:
        """Run negotiation inside a real Nitro Enclave.

        Secure flow:
        1. Launch enclave
        2. Start TCP tunnel (replaces old JSON proxy)
        3. Request attestation (includes enclave's ephemeral public key)
        4. Verify COSE signature + cert chain to AWS root CA
        5. Encrypt API key to enclave's public key (ECIES)
        6. Deliver encrypted API key
        7. Send negotiation inputs
        8. Wait for result
        9. Terminate
        """
        enclave_config = config.enclave_config or self._default_enclave_config()
        identity: EnclaveIdentity | None = None
        tunnel = None
        proxy = None
        start_time = time.monotonic()

        try:
            # Step 1: Launch enclave
            logger.info(
                "Launching Nitro enclave (cpu=%d mem=%dMiB eif=%s)",
                enclave_config.cpu_count,
                enclave_config.memory_mib,
                enclave_config.eif_path,
            )
            identity = await self._provider.launch_enclave(enclave_config)
            logger.info(
                "Nitro enclave launched: id=%s cid=%d",
                identity.enclave_id,
                identity.enclave_cid,
            )

            # Step 2: Start TCP tunnel (replaces old LLM proxy)
            tunnel = await self._start_tunnel(identity.enclave_cid)

            # Step 3: Request attestation
            nonce = os.urandom(32)
            # Request attestation through the provider
            attestation_response = await self._request_attestation(
                identity.enclave_id, nonce
            )

            # Step 4: Verify attestation with full COSE verification
            attestation = verify_attestation(
                attestation_response,
                expected_pcrs=config.expected_pcrs,
                nonce=nonce,
            )
            self._check_attestation(attestation)
            logger.info(
                "Nitro attestation verified (pcrs=%s, has_pubkey=%s)",
                {k: v[:16] + "..." for k, v in attestation.pcrs.items()},
                attestation.enclave_public_key is not None,
            )

            # Step 5+6: Encrypt and deliver API key
            nitro_api_key = config.api_key or config.anthropic_api_key
            if nitro_api_key and attestation.enclave_public_key:
                await self._deliver_api_key(
                    identity.enclave_id,
                    nitro_api_key,
                    attestation.enclave_public_key,
                )
            elif nitro_api_key:
                logger.warning(
                    "Attestation has no public key; falling back to proxy mode"
                )
                # Fall back to old proxy mode
                proxy = await self._start_llm_proxy(
                    identity.enclave_cid, nitro_api_key
                )

            # Step 7: Send negotiation inputs to the enclave
            negotiate_msg = {
                "action": "negotiate",
                "invention": {
                    "title": config.invention.title,
                    "full_description": config.invention.full_description,
                    "technical_domain": config.invention.technical_domain,
                    "novelty_claims": config.invention.novelty_claims,
                    "prior_art_known": config.invention.prior_art_known,
                    "potential_applications": config.invention.potential_applications,
                    "development_stage": config.invention.development_stage,
                    "self_assessed_value": config.invention.self_assessed_value,
                    "outside_option_value": config.invention.outside_option_value,
                    "confidential_sections": config.invention.confidential_sections,
                    "max_disclosure_fraction": config.invention.max_disclosure_fraction,
                },
                "budget_cap": config.budget_cap,
                "security_params": {
                    "k": config.security_params.k,
                    "p": config.security_params.p,
                    "c": config.security_params.c,
                    "gamma": config.security_params.gamma,
                },
                "max_rounds": config.max_rounds,
                "llm_provider": config.llm_provider,
                "llm_model": config.llm_model or config.anthropic_model,
            }

            logger.info("Sending negotiation inputs to enclave")
            await self._provider.send_message(identity.enclave_id, negotiate_msg)

            # Step 8: Wait for result with timeout
            timeout = self._settings.negotiation_timeout_sec
            logger.info("Waiting for enclave result (timeout=%ds)", timeout)

            response = await asyncio.wait_for(
                self._provider.receive_message(identity.enclave_id),
                timeout=timeout,
            )

            result = self._parse_enclave_response(response)
            elapsed = time.monotonic() - start_time
            logger.info(
                "Nitro negotiation complete: outcome=%s elapsed=%.1fs",
                result.outcome.value,
                elapsed,
            )
            return result

        except TimeoutError:
            elapsed = time.monotonic() - start_time
            logger.error("Nitro negotiation timed out after %.1fs", elapsed)
            return NegotiationResult(
                outcome=NegotiationOutcomeType.ERROR,
                final_price=None,
                omega_hat=0.0,
                theta=0.0,
                phi=0.0,
                seller_payoff=None,
                buyer_payoff=None,
                reason=f"Negotiation timed out after {elapsed:.0f}s",
            )
        except AttestationError:
            raise
        except TEEError:
            raise
        except Exception as exc:
            logger.error("Nitro orchestration failed: %s", exc, exc_info=True)
            raise OrchestrationError(
                f"Nitro negotiation failed: {exc}"
            ) from exc
        finally:
            # Step 9: Always clean up
            if proxy is not None:
                try:
                    await proxy.stop()
                    logger.info("LLM proxy stopped")
                except Exception as proxy_exc:
                    logger.warning("Failed to stop LLM proxy: %s", proxy_exc)

            if tunnel is not None:
                try:
                    await tunnel.stop()
                    logger.info(
                        "TCP tunnel stopped (%d bytes forwarded)",
                        tunnel.bytes_forwarded,
                    )
                except Exception as tunnel_exc:
                    logger.warning("Failed to stop tunnel: %s", tunnel_exc)

            if identity is not None:
                try:
                    await self._provider.terminate_enclave(identity.enclave_id)
                    logger.info("Nitro enclave terminated: %s", identity.enclave_id)
                except Exception as term_exc:
                    logger.warning(
                        "Failed to terminate Nitro enclave %s: %s",
                        identity.enclave_id,
                        term_exc,
                    )

    async def _start_tunnel(self, enclave_cid: int):
        """Start the TCP tunnel for Nitro mode.

        The tunnel forwards raw bytes between the enclave's vsock and
        remote TCP hosts. The enclave performs TLS itself.

        Returns:
            A VsockTunnel instance (with a stop() method for cleanup).
        """
        try:
            from ndai.enclave.vsock_tunnel import VsockTunnel
        except ImportError as exc:
            raise OrchestrationError(
                "vsock_tunnel module not available. Ensure ndai.enclave.vsock_tunnel "
                "is installed for Nitro mode."
            ) from exc

        tunnel = VsockTunnel()
        await tunnel.run_background()
        logger.info("TCP tunnel started for enclave cid=%d", enclave_cid)
        return tunnel

    async def _start_llm_proxy(self, enclave_cid: int, api_key: str):
        """Start the vsock LLM proxy for Nitro mode (fallback).

        The proxy forwards LLM API requests from the enclave to Anthropic,
        keeping the API key on the parent side. Less secure than tunnel mode
        because the parent sees plaintext.

        Returns:
            A VsockLLMProxy instance (with a stop() method for cleanup).
        """
        try:
            from ndai.enclave.vsock_proxy import VsockProxy
        except ImportError as exc:
            raise OrchestrationError(
                "vsock_proxy module not available. Ensure ndai.enclave.vsock_proxy "
                "is installed for Nitro mode."
            ) from exc

        proxy = VsockProxy(api_key=api_key)
        await proxy.run_background()
        logger.info("LLM proxy started for enclave cid=%d", enclave_cid)
        return proxy

    async def _request_attestation(
        self,
        enclave_id: str,
        nonce: bytes,
    ) -> bytes:
        """Request attestation from the enclave and extract the raw document.

        The enclave returns the attestation document as base64-encoded COSE Sign1.
        """
        attest_msg = {
            "action": "get_attestation",
            "nonce": nonce.hex(),
        }
        await self._provider.send_message(enclave_id, attest_msg)
        response = await self._provider.receive_message(enclave_id)

        if response.get("status") != "ok":
            error = response.get("error", "Unknown attestation error")
            raise AttestationError(f"Enclave attestation request failed: {error}")

        # Handle new format (base64-encoded COSE Sign1)
        attestation_b64 = response.get("attestation_doc")
        if attestation_b64:
            return base64.b64decode(attestation_b64)

        # Handle legacy format (raw JSON attestation from simulated provider)
        attestation_doc = await self._provider.get_attestation(enclave_id, nonce=nonce)
        return attestation_doc

    async def _deliver_api_key(
        self,
        enclave_id: str,
        api_key: str,
        enclave_public_key_der: bytes,
    ) -> None:
        """Encrypt the API key and deliver it to the enclave.

        The key is encrypted using ECIES with the enclave's ephemeral public
        key (extracted from the verified attestation document).
        """
        from ndai.enclave.ephemeral_keys import encrypt_api_key

        logger.info("Encrypting API key for enclave delivery")
        encrypted = encrypt_api_key(enclave_public_key_der, api_key)

        deliver_msg = {
            "action": "deliver_key",
            "encrypted_key": base64.b64encode(encrypted).decode("ascii"),
        }
        await self._provider.send_message(enclave_id, deliver_msg)
        response = await self._provider.receive_message(enclave_id)

        if response.get("status") != "ok":
            error = response.get("error", "Unknown key delivery error")
            raise OrchestrationError(f"API key delivery failed: {error}")

        logger.info("API key delivered to enclave successfully")

    def _check_attestation(self, result: AttestationResult) -> None:
        """Raise AttestationError if attestation verification failed."""
        if not result.valid:
            logger.error("Attestation verification failed: %s", result.error)
            raise AttestationError(
                f"Attestation verification failed: {result.error}"
            )

    def _parse_enclave_response(self, response: dict) -> NegotiationResult:
        """Parse the JSON response from the enclave into a NegotiationResult.

        The enclave wraps results as {"status": "ok", "result": {...}} or
        {"status": "error", "error": "..."}. Unwrap before parsing.
        """
        try:
            # Unwrap enclave envelope if present
            if "status" in response and "result" in response:
                if response["status"] != "ok":
                    error_msg = response.get("error", "Enclave returned error status")
                    return NegotiationResult(
                        outcome=NegotiationOutcomeType.ERROR,
                        final_price=None,
                        omega_hat=0.0,
                        theta=0.0,
                        phi=0.0,
                        seller_payoff=None,
                        buyer_payoff=None,
                        reason=error_msg,
                    )
                response = response["result"]
            elif "status" in response and response["status"] == "error":
                error_msg = response.get("error", "Enclave returned error")
                return NegotiationResult(
                    outcome=NegotiationOutcomeType.ERROR,
                    final_price=None,
                    omega_hat=0.0,
                    theta=0.0,
                    phi=0.0,
                    seller_payoff=None,
                    buyer_payoff=None,
                    reason=error_msg,
                )

            outcome_str = response.get("outcome", "error")
            try:
                outcome = NegotiationOutcomeType(outcome_str)
            except ValueError:
                logger.warning(
                    "Unknown outcome type '%s', treating as error", outcome_str
                )
                outcome = NegotiationOutcomeType.ERROR

            return NegotiationResult(
                outcome=outcome,
                final_price=response.get("final_price"),
                omega_hat=response.get("omega_hat", 0.0),
                theta=response.get("theta", 0.0),
                phi=response.get("phi", 0.0),
                seller_payoff=response.get("seller_payoff"),
                buyer_payoff=response.get("buyer_payoff"),
                buyer_valuation=response.get("buyer_valuation"),
                reason=response.get("reason", "No reason provided by enclave"),
            )
        except Exception as exc:
            logger.error("Failed to parse enclave response: %s", exc)
            return NegotiationResult(
                outcome=NegotiationOutcomeType.ERROR,
                final_price=None,
                omega_hat=0.0,
                theta=0.0,
                phi=0.0,
                seller_payoff=None,
                buyer_payoff=None,
                reason=f"Failed to parse enclave response: {exc}",
            )

    def _default_enclave_config(self) -> EnclaveConfig:
        """Build an EnclaveConfig from application settings."""
        return EnclaveConfig(
            cpu_count=self._settings.enclave_cpu_count,
            memory_mib=self._settings.enclave_memory_mib,
            eif_path=self._settings.enclave_eif_path,
            vsock_port=self._settings.enclave_vsock_port,
        )
