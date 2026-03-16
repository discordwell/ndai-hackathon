"""Integration tests for EnclaveOrchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ndai.config import Settings
from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    NegotiationResult,
    SecurityParams,
)
from ndai.tee.orchestrator import (
    AttestationError,
    EnclaveNegotiationConfig,
    EnclaveOrchestrator,
    OrchestrationError,
)
from ndai.tee.simulated_provider import SimulatedTEEProvider


@pytest.fixture
def invention():
    return InventionSubmission(
        title="Test Invention",
        full_description="A test invention for unit testing.",
        technical_domain="testing",
        novelty_claims=["Novel test approach"],
        prior_art_known=["Prior art A"],
        potential_applications=["Testing frameworks"],
        development_stage="prototype",
        self_assessed_value=0.75,
        outside_option_value=0.3,
        confidential_sections=["Secret sauce"],
        max_disclosure_fraction=0.8,
    )


@pytest.fixture
def security_params():
    return SecurityParams(k=3, p=0.005, c=7_500_000_000)


@pytest.fixture
def neg_config(invention, security_params):
    return EnclaveNegotiationConfig(
        invention=invention,
        budget_cap=1.0,
        security_params=security_params,
        max_rounds=2,
        anthropic_api_key="test-key-never-sent-to-enclave",
        anthropic_model="claude-sonnet-4-20250514",
    )


@pytest.fixture
def test_settings():
    return Settings(
        tee_mode="simulated",
        negotiation_timeout_sec=30,
        anthropic_api_key="test-key",
    )


class TestOrchestratorSimulatedMode:
    async def test_full_lifecycle_with_mock_session(
        self, neg_config, test_settings
    ):
        """Orchestrator launches enclave, verifies attestation, runs session, terminates."""
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        mock_result = NegotiationResult(
            outcome=NegotiationOutcomeType.AGREEMENT,
            final_price=0.45,
            omega_hat=0.6,
            theta=0.65,
            phi=100.0,
            seller_payoff=0.5,
            buyer_payoff=0.15,
            buyer_valuation=0.6,
            reason="Nash bargaining equilibrium reached",
        )

        with patch(
            "ndai.tee.orchestrator.NegotiationSession"
        ) as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.run.return_value = mock_result

            result = await orchestrator.run_negotiation(neg_config)

        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price == 0.45
        # Sensitive fields are stripped — parent should not see internals
        assert result.omega_hat == 0.0
        assert result.buyer_valuation is None
        assert result.seller_payoff is None
        assert result.buyer_payoff is None

        # Verify session was created with correct config (no API key leak check
        # is implicit — the enclave never receives it in simulated mode because
        # it runs in-process with the key)
        mock_session_cls.assert_called_once()
        call_config = mock_session_cls.call_args[0][0]
        assert call_config.invention.title == "Test Invention"
        assert call_config.budget_cap == 1.0
        assert call_config.max_rounds == 2

    async def test_enclave_terminated_on_success(
        self, neg_config, test_settings
    ):
        """Enclave is terminated after successful negotiation."""
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with patch("ndai.tee.orchestrator.NegotiationSession") as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.run.return_value = NegotiationResult(
                outcome=NegotiationOutcomeType.NO_DEAL,
                final_price=None,
                omega_hat=0.5,
                theta=0.65,
                phi=100.0,
                seller_payoff=None,
                buyer_payoff=None,
                reason="Budget exceeded",
            )

            await orchestrator.run_negotiation(neg_config)

        # After run, no enclaves should remain active
        assert len(provider._enclaves) == 0

    async def test_enclave_terminated_on_error(
        self, neg_config, test_settings
    ):
        """Enclave is terminated even when the session raises an exception."""
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with patch("ndai.tee.orchestrator.NegotiationSession") as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.run.side_effect = RuntimeError("LLM exploded")

            with pytest.raises(OrchestrationError, match="LLM exploded"):
                await orchestrator.run_negotiation(neg_config)

        # Enclave must still be terminated
        assert len(provider._enclaves) == 0

    async def test_timeout_returns_error_result(
        self, neg_config, test_settings
    ):
        """Timeout produces an ERROR NegotiationResult instead of raising."""
        import time as _time

        test_settings.negotiation_timeout_sec = 1
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with patch("ndai.tee.orchestrator.NegotiationSession") as mock_session_cls:
            mock_instance = mock_session_cls.return_value

            # run() is called in a thread via to_thread, so a blocking sleep works
            mock_instance.run.side_effect = lambda: _time.sleep(10)

            result = await orchestrator.run_negotiation(neg_config)

        assert result.outcome == NegotiationOutcomeType.ERROR
        assert "timed out" in result.reason

    async def test_attestation_pcr_mismatch_raises(
        self, neg_config, test_settings
    ):
        """Mismatched expected PCRs should raise AttestationError."""
        neg_config.expected_pcrs = {0: "definitely_wrong_pcr_value"}
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with pytest.raises(AttestationError, match="PCR0 mismatch"):
            await orchestrator.run_negotiation(neg_config)

        # Enclave should still be cleaned up
        assert len(provider._enclaves) == 0

    async def test_attestation_with_matching_pcrs(
        self, neg_config, test_settings
    ):
        """Matching expected PCRs should pass attestation."""
        import hashlib

        # Compute expected PCRs for simulated provider with default eif_path
        seed = test_settings.enclave_eif_path.encode()
        expected_pcr0 = hashlib.sha384(b"pcr0:" + seed).hexdigest()

        neg_config.expected_pcrs = {0: expected_pcr0}
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with patch("ndai.tee.orchestrator.NegotiationSession") as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.run.return_value = NegotiationResult(
                outcome=NegotiationOutcomeType.AGREEMENT,
                final_price=0.3,
                omega_hat=0.5,
                theta=0.65,
                phi=100.0,
                seller_payoff=0.4,
                buyer_payoff=0.2,
                reason="Deal reached",
            )

            result = await orchestrator.run_negotiation(neg_config)

        assert result.outcome == NegotiationOutcomeType.AGREEMENT


class TestOrchestratorResponseParsing:
    """Test _parse_enclave_response directly for Nitro response format."""

    def test_parse_agreement(self, test_settings):
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        response = {
            "outcome": "agreement",
            "final_price": 0.45,
            "omega_hat": 0.6,
            "theta": 0.65,
            "phi": 100.0,
            "seller_payoff": 0.5,
            "buyer_payoff": 0.15,
            "buyer_valuation": 0.6,
            "reason": "Nash bargaining equilibrium reached",
        }
        result = orchestrator._parse_enclave_response(response)
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price == 0.45
        assert result.omega_hat == 0.6
        assert result.buyer_valuation == 0.6

    def test_parse_no_deal(self, test_settings):
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        response = {
            "outcome": "no_deal",
            "final_price": None,
            "omega_hat": 0.5,
            "theta": 0.65,
            "phi": 100.0,
            "seller_payoff": None,
            "buyer_payoff": None,
            "reason": "Budget exceeded",
        }
        result = orchestrator._parse_enclave_response(response)
        assert result.outcome == NegotiationOutcomeType.NO_DEAL
        assert result.final_price is None

    def test_parse_error(self, test_settings):
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        response = {
            "outcome": "error",
            "reason": "Enclave crashed",
        }
        result = orchestrator._parse_enclave_response(response)
        assert result.outcome == NegotiationOutcomeType.ERROR
        assert result.omega_hat == 0.0  # defaults

    def test_parse_unknown_outcome(self, test_settings):
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        response = {"outcome": "unknown_value", "reason": "???"}
        result = orchestrator._parse_enclave_response(response)
        assert result.outcome == NegotiationOutcomeType.ERROR

    def test_parse_empty_response(self, test_settings):
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        result = orchestrator._parse_enclave_response({})
        assert result.outcome == NegotiationOutcomeType.ERROR


class TestOrchestratorNitroMode:
    """Test Nitro-specific orchestration paths (mocked provider)."""

    async def test_nitro_sends_correct_message(
        self, neg_config, test_settings
    ):
        """Verify the message sent to the enclave has correct structure and no API key."""
        import base64

        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        from ndai.tee.attestation import AttestationResult
        from ndai.tee.provider import EnclaveIdentity, TEEProvider, TEEType

        provider = AsyncMock(spec=TEEProvider)
        provider.get_tee_type = MagicMock(return_value=TEEType.NITRO)

        identity = EnclaveIdentity(
            enclave_id="nitro-test",
            enclave_cid=10,
            pcr0="aa",
            pcr1="bb",
            pcr2="cc",
            tee_type=TEEType.NITRO,
        )
        provider.launch_enclave.return_value = identity

        fixed_nonce = b"\x00" * 32

        # Generate a test ephemeral public key
        test_key = ec.generate_private_key(ec.SECP384R1())
        test_pubkey_der = test_key.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )

        # Build a stub attestation doc WITH public key
        from ndai.enclave.nsm_stub import NSMStub
        stub = NSMStub(eif_path="test.eif")
        attestation_doc = stub.get_attestation(
            nonce=fixed_nonce, public_key=test_pubkey_der
        )
        attestation_b64 = base64.b64encode(attestation_doc).decode("ascii")

        # Mock attestation verification to return valid result with pubkey
        mock_attestation = AttestationResult(
            valid=True,
            pcrs={0: "aa", 1: "bb", 2: "cc"},
            enclave_cid=10,
            timestamp=None,
            enclave_public_key=test_pubkey_der,
        )

        # Sequence of receive_message calls:
        # 1. Attestation response with COSE doc
        # 2. Key delivery ack
        # 3. Negotiation result
        receive_side_effects = [
            {"status": "ok", "attestation_doc": attestation_b64},
            {"status": "ok"},
            {
                "status": "ok",
                "result": {
                    "outcome": "agreement",
                    "final_price": 0.3,
                    "reason": "Deal",
                },
            },
        ]
        provider.receive_message.side_effect = receive_side_effects

        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with (
            patch("ndai.tee.orchestrator.os.urandom", return_value=fixed_nonce),
            patch("ndai.tee.orchestrator.verify_attestation", return_value=mock_attestation),
            patch("ndai.tee.orchestrator.EnclaveOrchestrator._start_tunnel") as mock_tunnel,
        ):
            mock_tunnel_instance = AsyncMock()
            mock_tunnel_instance.bytes_forwarded = 0
            mock_tunnel.return_value = mock_tunnel_instance

            result = await orchestrator.run_negotiation(neg_config)

        assert result.outcome == NegotiationOutcomeType.AGREEMENT

        # Find the negotiate message among all send_message calls
        negotiate_msg = None
        for call in provider.send_message.call_args_list:
            msg = call[0][1]
            if msg.get("action") == "negotiate":
                negotiate_msg = msg
                break
        assert negotiate_msg is not None

        assert negotiate_msg["invention"]["title"] == "Test Invention"
        assert negotiate_msg["budget_cap"] == 1.0
        assert negotiate_msg["security_params"]["k"] == 3
        assert negotiate_msg["max_rounds"] == 2
        assert negotiate_msg["llm_model"] == "claude-sonnet-4-20250514"

        # API key must NOT be in the message to the enclave
        assert "anthropic_api_key" not in negotiate_msg
        assert "api_key" not in negotiate_msg

        # Tunnel started and stopped
        mock_tunnel.assert_called_once()
        mock_tunnel_instance.stop.assert_called_once()

        # Enclave terminated
        provider.terminate_enclave.assert_called_once_with("nitro-test")

    async def test_nitro_fails_closed_without_pubkey(
        self, neg_config, test_settings
    ):
        """Nitro mode raises OrchestrationError when attestation lacks public key."""
        from ndai.tee.attestation import AttestationResult
        from ndai.tee.provider import EnclaveIdentity, TEEProvider, TEEType

        provider = AsyncMock(spec=TEEProvider)
        provider.get_tee_type = MagicMock(return_value=TEEType.NITRO)

        identity = EnclaveIdentity(
            enclave_id="nitro-no-pubkey",
            enclave_cid=10,
            pcr0="aa",
            pcr1="bb",
            pcr2="cc",
            tee_type=TEEType.NITRO,
        )
        provider.launch_enclave.return_value = identity

        fixed_nonce = b"\x00" * 32

        # Mock attestation that is valid but has NO public key
        mock_attestation = AttestationResult(
            valid=True,
            pcrs={0: "aa", 1: "bb", 2: "cc"},
            enclave_cid=10,
            timestamp=None,
            enclave_public_key=None,  # <-- no public key
        )

        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with (
            patch("ndai.tee.orchestrator.os.urandom", return_value=fixed_nonce),
            patch.object(
                orchestrator, "_request_attestation",
                new_callable=AsyncMock, return_value=b"fake-attestation-bytes",
            ),
            patch("ndai.tee.orchestrator.verify_attestation", return_value=mock_attestation),
            patch("ndai.tee.orchestrator.EnclaveOrchestrator._start_tunnel") as mock_tunnel,
        ):
            mock_tunnel_instance = AsyncMock()
            mock_tunnel_instance.bytes_forwarded = 0
            mock_tunnel.return_value = mock_tunnel_instance

            with pytest.raises(OrchestrationError, match="no enclave public key"):
                await orchestrator.run_negotiation(neg_config)

        # Enclave must still be terminated
        provider.terminate_enclave.assert_called_once_with("nitro-no-pubkey")

    async def test_simulated_result_stripped(
        self, neg_config, test_settings
    ):
        """Simulated mode strips sensitive fields from result."""
        provider = SimulatedTEEProvider()
        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        mock_result = NegotiationResult(
            outcome=NegotiationOutcomeType.AGREEMENT,
            final_price=0.45,
            omega_hat=0.6,
            theta=0.65,
            phi=100.0,
            seller_payoff=0.5,
            buyer_payoff=0.15,
            buyer_valuation=0.6,
            reason="Nash bargaining equilibrium reached",
        )

        with patch(
            "ndai.tee.orchestrator.NegotiationSession"
        ) as mock_session_cls:
            mock_instance = mock_session_cls.return_value
            mock_instance.run.return_value = mock_result

            result = await orchestrator.run_negotiation(neg_config)

        # Result should have outcome and final_price preserved
        assert result.outcome == NegotiationOutcomeType.AGREEMENT
        assert result.final_price == 0.45
        assert result.reason == "Nash bargaining equilibrium reached"

        # Sensitive internals should be zeroed/None
        assert result.omega_hat == 0.0
        assert result.theta == 0.0
        assert result.phi == 0.0
        assert result.seller_payoff is None
        assert result.buyer_payoff is None
        assert result.buyer_valuation is None

    async def test_nitro_terminates_on_tunnel_import_error(
        self, neg_config, test_settings
    ):
        """If vsock_tunnel import fails, enclave is still terminated."""
        from ndai.tee.provider import EnclaveIdentity, TEEType

        provider = AsyncMock()
        provider.get_tee_type = MagicMock(return_value=TEEType.NITRO)

        identity = EnclaveIdentity(
            enclave_id="nitro-cleanup",
            enclave_cid=10,
            pcr0="aa",
            pcr1="bb",
            pcr2="cc",
            tee_type=TEEType.NITRO,
        )
        provider.launch_enclave.return_value = identity

        orchestrator = EnclaveOrchestrator(provider=provider, settings=test_settings)

        with patch(
            "ndai.tee.orchestrator.EnclaveOrchestrator._start_tunnel",
            side_effect=OrchestrationError("vsock_tunnel not available"),
        ):
            with pytest.raises(OrchestrationError, match="vsock_tunnel"):
                await orchestrator.run_negotiation(neg_config)

        # Enclave must still be terminated
        provider.terminate_enclave.assert_called_once_with("nitro-cleanup")
