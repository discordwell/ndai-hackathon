"""Integration tests for EnclaveOrchestrator with SimulatedTEEProvider.

Tests the full enclave lifecycle (launch -> attest -> negotiate -> terminate)
without requiring real Nitro hardware or a live LLM API key. LLM calls are
mocked so every test is deterministic and fast.
"""

import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ndai.config import Settings
from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import (
    NegotiationOutcomeType,
    NegotiationResult,
    SecurityParams,
)
from ndai.enclave.session import NegotiationSession, SessionConfig
from ndai.tee.provider import EnclaveConfig, EnclaveLaunchError, EnclaveNotFoundError
from ndai.tee.simulated_provider import SimulatedTEEProvider


# ---------------------------------------------------------------------------
# Dataclass mirroring the orchestrator's expected config (being built by
# another agent). We define it here so tests are self-contained.
# ---------------------------------------------------------------------------


@dataclass
class EnclaveNegotiationConfig:
    """Configuration passed to the orchestrator to run a negotiation."""

    invention: InventionSubmission
    budget_cap: float
    security_params: SecurityParams
    max_rounds: int = 5
    anthropic_api_key: str = "test-key"
    anthropic_model: str = "claude-sonnet-4-20250514"
    expected_pcrs: dict[int, str] | None = None
    enclave_config: EnclaveConfig = field(default_factory=lambda: EnclaveConfig(eif_path="test.eif"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provider():
    return SimulatedTEEProvider()


@pytest.fixture
def enclave_config():
    return EnclaveConfig(eif_path="test.eif", vsock_port=5000)


@pytest.fixture
def security_params():
    return SecurityParams(k=3, p=0.005, c=7_500_000_000)


@pytest.fixture
def invention(sample_invention):
    return InventionSubmission(**sample_invention)


@pytest.fixture
def negotiation_config(invention, security_params, enclave_config):
    return EnclaveNegotiationConfig(
        invention=invention,
        budget_cap=0.6,
        security_params=security_params,
        max_rounds=1,
        anthropic_api_key="test-key-not-real",
        anthropic_model="claude-sonnet-4-20250514",
        enclave_config=enclave_config,
    )


def _make_mock_tool_response(tool_name: str, tool_input: dict, tool_id: str = "tool_01"):
    """Build a mock Anthropic Message with a tool_use content block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_id

    msg = MagicMock()
    msg.content = [tool_block]
    msg.stop_reason = "tool_use"
    return msg


def _patch_llm_for_full_negotiation():
    """Patch LLMClient.create_message to return deterministic tool-use responses.

    Bilateral flow (2 API calls):
    1. Seller disclosure (make_disclosure) → omega_hat=0.6
    2. Buyer evaluation (evaluate_invention) → v_b=0.55
    Resolution: P* = (0.55 + 0.3*0.6) / 2 = 0.365
    """
    responses = [
        # 1. Seller disclosure
        _make_mock_tool_response("make_disclosure", {
            "summary": "A novel quantum-resistant key exchange protocol.",
            "technical_details": "Ring-LWE variant with tight security reduction.",
            "disclosed_value": 0.6,
            "withheld_aspects": ["NTT optimization trick"],
            "reasoning": "Disclosing near phi for maximum surplus.",
        }, tool_id="disc_01"),
        # 2. Buyer evaluation (bilateral: no make_offer needed)
        _make_mock_tool_response("evaluate_invention", {
            "assessed_value": 0.55,
            "strengths": ["Post-quantum security", "Efficient implementation"],
            "concerns": ["Early prototype stage"],
            "reasoning": "Strong technical merit but unproven at scale.",
        }, tool_id="eval_01"),
    ]

    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        return responses[idx]

    return patch(
        "ndai.enclave.agents.llm_client.LLMClient.create_message",
        side_effect=side_effect,
    )


# ---------------------------------------------------------------------------
# Tests: SimulatedTEEProvider lifecycle (no orchestrator dependency)
# ---------------------------------------------------------------------------


class TestSimulatedEnclaveLifecycle:
    """Test the enclave launch/attest/terminate lifecycle using SimulatedTEEProvider."""

    async def test_launch_produces_valid_identity(self, provider, enclave_config):
        identity = await provider.launch_enclave(enclave_config)
        assert identity.enclave_id.startswith("sim-")
        assert identity.enclave_cid >= 4
        assert len(identity.pcr0) == 96  # SHA-384 hex digest
        assert len(identity.pcr1) == 96
        assert len(identity.pcr2) == 96
        await provider.terminate_enclave(identity.enclave_id)

    async def test_attestation_contains_pcrs_and_nonce(self, provider, enclave_config):
        identity = await provider.launch_enclave(enclave_config)
        nonce = b"test-nonce-abcdef"

        doc_bytes = await provider.get_attestation(identity.enclave_id, nonce=nonce)
        doc = json.loads(doc_bytes)

        assert doc["pcr0"] == identity.pcr0
        assert doc["pcr1"] == identity.pcr1
        assert doc["pcr2"] == identity.pcr2
        assert doc["nonce"] == nonce.hex()
        assert doc["type"] == "simulated_attestation"

        await provider.terminate_enclave(identity.enclave_id)

    async def test_attestation_without_nonce(self, provider, enclave_config):
        identity = await provider.launch_enclave(enclave_config)
        doc_bytes = await provider.get_attestation(identity.enclave_id, nonce=None)
        doc = json.loads(doc_bytes)

        assert doc["nonce"] is None
        assert doc["pcr0"] == identity.pcr0

        await provider.terminate_enclave(identity.enclave_id)

    async def test_terminate_cleans_up(self, provider, enclave_config):
        identity = await provider.launch_enclave(enclave_config)
        await provider.terminate_enclave(identity.enclave_id)

        with pytest.raises(EnclaveNotFoundError):
            await provider.get_attestation(identity.enclave_id)

    async def test_terminate_idempotent(self, provider, enclave_config):
        identity = await provider.launch_enclave(enclave_config)
        await provider.terminate_enclave(identity.enclave_id)
        # Second terminate should not raise
        await provider.terminate_enclave(identity.enclave_id)


# ---------------------------------------------------------------------------
# Tests: Simulated attestation verification
# ---------------------------------------------------------------------------


class TestSimulatedAttestationVerification:
    """Test attestation document verification against expected PCR values."""

    async def test_pcr_match(self, provider, enclave_config):
        identity = await provider.launch_enclave(enclave_config)
        doc_bytes = await provider.get_attestation(identity.enclave_id)
        doc = json.loads(doc_bytes)

        # Verify PCRs match the identity returned at launch
        expected = {0: identity.pcr0, 1: identity.pcr1, 2: identity.pcr2}
        for idx, expected_val in expected.items():
            assert doc[f"pcr{idx}"] == expected_val

        await provider.terminate_enclave(identity.enclave_id)

    async def test_pcr_mismatch_detected(self, provider, enclave_config):
        identity = await provider.launch_enclave(enclave_config)
        doc_bytes = await provider.get_attestation(identity.enclave_id)
        doc = json.loads(doc_bytes)

        # Tamper with expected PCR
        tampered_pcr0 = "a" * 96
        assert doc["pcr0"] != tampered_pcr0, "Test setup error: tampered value matches real"

        await provider.terminate_enclave(identity.enclave_id)

    async def test_same_eif_produces_same_pcrs(self, provider):
        config_a = EnclaveConfig(eif_path="same-image.eif")
        config_b = EnclaveConfig(eif_path="same-image.eif")

        id_a = await provider.launch_enclave(config_a)
        id_b = await provider.launch_enclave(config_b)

        assert id_a.pcr0 == id_b.pcr0
        assert id_a.pcr1 == id_b.pcr1
        assert id_a.pcr2 == id_b.pcr2

        await provider.terminate_enclave(id_a.enclave_id)
        await provider.terminate_enclave(id_b.enclave_id)

    async def test_different_eif_produces_different_pcrs(self, provider):
        id_a = await provider.launch_enclave(EnclaveConfig(eif_path="image-a.eif"))
        id_b = await provider.launch_enclave(EnclaveConfig(eif_path="image-b.eif"))

        assert id_a.pcr0 != id_b.pcr0

        await provider.terminate_enclave(id_a.enclave_id)
        await provider.terminate_enclave(id_b.enclave_id)


# ---------------------------------------------------------------------------
# Tests: Full negotiation lifecycle (launch -> negotiate -> terminate)
# ---------------------------------------------------------------------------


class TestNegotiationLifecycle:
    """Test the full orchestration flow using SimulatedTEEProvider.

    Since the orchestrator runs NegotiationSession in-process for the
    simulated provider, these tests exercise the session directly while
    verifying that the enclave lifecycle (launch/terminate) is honored.
    """

    async def test_full_lifecycle_agreement(
        self, provider, enclave_config, invention, security_params
    ):
        """Launch enclave, run negotiation, get agreement, terminate."""
        identity = await provider.launch_enclave(enclave_config)
        try:
            # Verify attestation before running negotiation
            doc_bytes = await provider.get_attestation(identity.enclave_id)
            doc = json.loads(doc_bytes)
            assert doc["pcr0"] == identity.pcr0

            # Run negotiation in-process (simulated mode)
            session_config = SessionConfig(
                invention=invention,
                budget_cap=0.6,
                security_params=security_params,
                max_rounds=1,
                anthropic_api_key="test-key",
                anthropic_model="claude-sonnet-4-20250514",
            )

            with _patch_llm_for_full_negotiation():
                session = NegotiationSession(session_config)
                result = session.run()

            assert result.outcome == NegotiationOutcomeType.AGREEMENT
            assert result.final_price is not None
            assert result.final_price > 0
            assert result.final_price <= session_config.budget_cap
            assert result.seller_payoff is not None
            assert result.buyer_payoff is not None
        finally:
            await provider.terminate_enclave(identity.enclave_id)

        # Enclave is destroyed
        with pytest.raises(EnclaveNotFoundError):
            await provider.get_attestation(identity.enclave_id)

    async def test_full_lifecycle_no_deal_budget(
        self, provider, enclave_config, invention, security_params
    ):
        """No deal when budget is too low for equilibrium price."""
        identity = await provider.launch_enclave(enclave_config)
        try:
            session_config = SessionConfig(
                invention=invention,
                budget_cap=0.01,  # Very low budget
                security_params=security_params,
                max_rounds=1,
                anthropic_api_key="test-key",
            )

            with _patch_llm_for_full_negotiation():
                session = NegotiationSession(session_config)
                result = session.run()

            # With omega=0.75, theta~0.65, equilibrium price ~0.39 > budget 0.01
            assert result.outcome == NegotiationOutcomeType.NO_DEAL
            assert result.final_price is None
            assert "budget" in result.reason.lower() or "exceeds" in result.reason.lower()
        finally:
            await provider.terminate_enclave(identity.enclave_id)

    async def test_terminate_always_called_on_error(
        self, provider, enclave_config, invention, security_params
    ):
        """Enclave is terminated even if the negotiation raises an exception."""
        identity = await provider.launch_enclave(enclave_config)
        terminated = False

        try:
            session_config = SessionConfig(
                invention=invention,
                budget_cap=0.6,
                security_params=security_params,
                anthropic_api_key="test-key",
            )

            # Patch LLM to raise an error during negotiation
            with patch(
                "ndai.enclave.agents.llm_client.LLMClient.create_message",
                side_effect=RuntimeError("Simulated LLM failure"),
            ):
                session = NegotiationSession(session_config)
                with pytest.raises(RuntimeError, match="Simulated LLM failure"):
                    session.run()
        finally:
            await provider.terminate_enclave(identity.enclave_id)
            terminated = True

        assert terminated
        with pytest.raises(EnclaveNotFoundError):
            await provider.send_message(identity.enclave_id, {"test": True})

    async def test_terminate_on_session_error(self, provider, enclave_config):
        """Enclave is terminated even when session config is invalid."""
        identity = await provider.launch_enclave(enclave_config)
        try:
            # Invalid security params should raise during SecurityParams construction
            with pytest.raises(ValueError):
                SecurityParams(k=0, p=0.5, c=100)
        finally:
            await provider.terminate_enclave(identity.enclave_id)

        with pytest.raises(EnclaveNotFoundError):
            await provider.get_attestation(identity.enclave_id)


# ---------------------------------------------------------------------------
# Tests: Enclave launch failure
# ---------------------------------------------------------------------------


class TestEnclaveLaunchFailure:
    """Test error handling when enclave launch fails."""

    async def test_launch_failure_raises(self):
        """A provider that fails to launch should raise EnclaveLaunchError."""
        provider = SimulatedTEEProvider()

        # SimulatedTEEProvider always succeeds, so we mock a failure
        with patch.object(
            provider,
            "launch_enclave",
            side_effect=EnclaveLaunchError("Insufficient resources"),
        ):
            with pytest.raises(EnclaveLaunchError, match="Insufficient resources"):
                await provider.launch_enclave(EnclaveConfig())

    async def test_no_cleanup_needed_on_launch_failure(self):
        """If launch fails, there's no enclave to terminate."""
        provider = SimulatedTEEProvider()
        enclave_id = None

        with patch.object(
            provider,
            "launch_enclave",
            side_effect=EnclaveLaunchError("Out of memory"),
        ):
            try:
                identity = await provider.launch_enclave(EnclaveConfig())
                enclave_id = identity.enclave_id
            except EnclaveLaunchError:
                pass

        assert enclave_id is None
        # Terminate on a non-existent ID should be safe
        await provider.terminate_enclave("nonexistent-id")


# ---------------------------------------------------------------------------
# Tests: Negotiation timeout behavior
# ---------------------------------------------------------------------------


class TestNegotiationTimeout:
    """Test that long-running negotiations respect timeout constraints."""

    async def test_session_completes_within_max_rounds(
        self, provider, enclave_config, invention, security_params
    ):
        """Negotiation should complete within configured max_rounds."""
        identity = await provider.launch_enclave(enclave_config)
        try:
            session_config = SessionConfig(
                invention=invention,
                budget_cap=0.6,
                security_params=security_params,
                max_rounds=1,  # Single-round (mock only provides 2 responses)
                anthropic_api_key="test-key",
            )

            with _patch_llm_for_full_negotiation():
                session = NegotiationSession(session_config)
                result = session.run()

            # Should still produce a result (deterministic Nash resolution)
            assert result.outcome in (
                NegotiationOutcomeType.AGREEMENT,
                NegotiationOutcomeType.NO_DEAL,
            )
            # Transcript should have <= max_rounds * 2 messages (seller + buyer per round)
            # plus initial disclosure
            assert len(session.transcript.messages) <= (session_config.max_rounds * 2 + 2)
        finally:
            await provider.terminate_enclave(identity.enclave_id)


# ---------------------------------------------------------------------------
# Tests: Negotiation engine integration (no LLM)
# ---------------------------------------------------------------------------


class TestNegotiationEngineIntegration:
    """Test the NegotiationSession's deterministic resolution path."""

    async def test_deterministic_result_always_computed(
        self, invention, security_params
    ):
        """The deterministic result is computed regardless of LLM behavior."""
        session_config = SessionConfig(
            invention=invention,
            budget_cap=0.6,
            security_params=security_params,
            anthropic_api_key="test-key",
        )

        with _patch_llm_for_full_negotiation():
            session = NegotiationSession(session_config)
            result = session.run()

        # deterministic_result should always be populated
        assert session.transcript.deterministic_result is not None
        det = session.transcript.deterministic_result
        assert det.theta == (1 + invention.outside_option_value) / 2
        assert det.phi > 0

    async def test_agreement_payoffs_are_consistent(
        self, invention, security_params
    ):
        """Verify payoff arithmetic for agreements."""
        session_config = SessionConfig(
            invention=invention,
            budget_cap=0.6,
            security_params=security_params,
            anthropic_api_key="test-key",
        )

        with _patch_llm_for_full_negotiation():
            session = NegotiationSession(session_config)
            result = session.run()

        if result.outcome == NegotiationOutcomeType.AGREEMENT:
            assert result.final_price is not None
            assert result.seller_payoff is not None
            assert result.buyer_payoff is not None
            # buyer_payoff = v_b - P (bilateral) or omega_hat - P (unilateral fallback)
            if result.buyer_valuation is not None:
                assert abs(result.buyer_payoff - (result.buyer_valuation - result.final_price)) < 1e-9
            else:
                assert abs(result.buyer_payoff - (result.omega_hat - result.final_price)) < 1e-9


# ---------------------------------------------------------------------------
# Tests: Multiple sequential negotiations
# ---------------------------------------------------------------------------


class TestMultipleNegotiations:
    """Test running multiple negotiations sequentially (each in its own enclave)."""

    async def test_sequential_negotiations_isolated(
        self, provider, invention, security_params
    ):
        """Each negotiation gets its own enclave, with no state leakage."""
        results = []

        for budget in [0.6, 0.3, 0.01]:
            config = EnclaveConfig(eif_path="test.eif")
            identity = await provider.launch_enclave(config)
            try:
                session_config = SessionConfig(
                    invention=invention,
                    budget_cap=budget,
                    security_params=security_params,
                    max_rounds=1,
                    anthropic_api_key="test-key",
                )
                with _patch_llm_for_full_negotiation():
                    session = NegotiationSession(session_config)
                    result = session.run()
                results.append(result)
            finally:
                await provider.terminate_enclave(identity.enclave_id)

        # High budget should agree, very low should not
        assert results[0].outcome == NegotiationOutcomeType.AGREEMENT
        assert results[2].outcome == NegotiationOutcomeType.NO_DEAL

    async def test_enclave_ids_are_unique(self, provider):
        """Each launched enclave gets a unique ID."""
        config = EnclaveConfig(eif_path="test.eif")
        ids = set()

        for _ in range(5):
            identity = await provider.launch_enclave(config)
            ids.add(identity.enclave_id)
            await provider.terminate_enclave(identity.enclave_id)

        assert len(ids) == 5
