"""Tests for the verification verdict: 'did the exploit meet its CLAIM?'

The orchestrator collapses the enclave's CapabilityResult into the boolean
``unpatched_matches`` that drives the user-facing passed/failed status and the
on-chain commitment. Previously that boolean was ``verified_level is not None``
— i.e. *any* capability passed, so a PoC claiming LPE that only crashed the
target was reported as a successful verification. These tests pin the corrected
behaviour: the verified level must actually satisfy the claimed level.
"""

import pytest

from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    CapabilityResult,
    ClaimedCapability,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
    VerificationResult,
)
from ndai.tee import vuln_verify_orchestrator as vvo
from ndai.tee.attestation import AttestationResult
from ndai.tee.provider import EnclaveConfig, EnclaveIdentity, TEEProvider, TEEType


class TestCapabilityMeetsClaim:
    @pytest.mark.parametrize(
        "verified,claimed,expected",
        [
            # Nothing verified never satisfies a claim.
            (None, CapabilityLevel.CRASH, False),
            (None, CapabilityLevel.ACE, False),
            # Exact matches pass.
            (CapabilityLevel.CRASH, CapabilityLevel.CRASH, True),
            (CapabilityLevel.ACE, CapabilityLevel.ACE, True),
            (CapabilityLevel.LPE, CapabilityLevel.LPE, True),
            # The headline bug: claim LPE, only crash → must NOT pass.
            (CapabilityLevel.CRASH, CapabilityLevel.LPE, False),
            (CapabilityLevel.ACE, CapabilityLevel.LPE, False),
            (CapabilityLevel.INFO_LEAK, CapabilityLevel.ACE, False),
            # A stronger capability satisfies a weaker claim.
            (CapabilityLevel.LPE, CapabilityLevel.ACE, True),
            (CapabilityLevel.CALLBACK, CapabilityLevel.ACE, True),
            (CapabilityLevel.DOS, CapabilityLevel.CRASH, True),
            (CapabilityLevel.ACE, CapabilityLevel.INFO_LEAK, True),
            # Callback claimed but only (lesser) ACE proven → fail.
            (CapabilityLevel.ACE, CapabilityLevel.CALLBACK, False),
        ],
    )
    def test_meets_claim(self, verified, claimed, expected):
        from ndai.enclave.vuln_verify.protocol import capability_meets_claim

        assert capability_meets_claim(verified, claimed) is expected


class TestLevelFromValue:
    def test_known_value(self):
        assert vvo._level_from_value("ace") == CapabilityLevel.ACE
        assert vvo._level_from_value("lpe") == CapabilityLevel.LPE

    def test_none_and_empty(self):
        assert vvo._level_from_value(None) is None
        assert vvo._level_from_value("") is None

    def test_unknown_fails_closed(self):
        assert vvo._level_from_value("bogus") is None


def _make_spec(level: CapabilityLevel) -> TargetSpec:
    return TargetSpec(
        spec_id="verdict-spec",
        base_image="ubuntu:22.04",
        packages=[],
        config_files=[],
        services=[ServiceSpec("svc", "true", "true")],
        poc=PoCSpec("bash", "true"),
        claimed_capability=ClaimedCapability(level=level),
    )


def _result(claimed: CapabilityLevel, verified: CapabilityLevel | None) -> VerificationResult:
    return VerificationResult(
        spec_id="verdict-spec",
        unpatched_capability=CapabilityResult(claimed=claimed, verified_level=verified),
        patched_capability=None,
        overlap_detected=None,
        verification_chain_hash="abc123",
        timestamp="2026-01-01T00:00:00Z",
    )


class FakeSimProvider(TEEProvider):
    """In-process provider that satisfies the simulated orchestration path."""

    def __init__(self) -> None:
        self.terminated: list[str] = []

    def get_tee_type(self) -> TEEType:
        return TEEType.SIMULATED

    async def launch_enclave(self, config: EnclaveConfig) -> EnclaveIdentity:
        return EnclaveIdentity(
            enclave_id="sim-1",
            enclave_cid=3,
            pcr0="00" * 48,
            pcr1="11" * 48,
            pcr2="22" * 48,
            tee_type=TEEType.SIMULATED,
        )

    async def get_attestation(self, enclave_id: str, nonce: bytes | None = None) -> bytes:
        return b"sim-doc"

    async def send_message(self, enclave_id: str, message: dict) -> None:  # pragma: no cover
        pass

    async def receive_message(self, enclave_id: str) -> dict:  # pragma: no cover
        return {"status": "ok"}

    async def terminate_enclave(self, enclave_id: str) -> None:
        self.terminated.append(enclave_id)


async def _run_simulated_verdict(monkeypatch, claimed, verified):
    """Drive the real _run_simulated path with a crafted protocol result."""
    from ndai.enclave.vuln_verify.protocol import VulnVerificationProtocol

    def fake_verify(doc, expected_pcrs=None, nonce=None, **kwargs):
        return AttestationResult(
            valid=True,
            pcrs={0: "00" * 48},
            enclave_cid=3,
            timestamp=None,
            enclave_public_key=None,
        )

    monkeypatch.setattr(vvo, "verify_attestation", fake_verify)
    monkeypatch.setattr(
        VulnVerificationProtocol, "run", lambda self: _result(claimed, verified)
    )

    provider = FakeSimProvider()
    orch = vvo.VulnVerifyOrchestrator(provider)
    config = vvo.VerificationConfig(target_spec=_make_spec(claimed))
    outcome = await orch.run_verification(config)
    assert provider.terminated == ["sim-1"]
    return outcome


class TestOrchestratorVerdict:
    async def test_claim_lpe_only_crash_fails(self, monkeypatch):
        outcome = await _run_simulated_verdict(
            monkeypatch, CapabilityLevel.LPE, CapabilityLevel.CRASH
        )
        assert outcome.unpatched_matches is False

    async def test_claim_ace_verified_ace_passes(self, monkeypatch):
        outcome = await _run_simulated_verdict(
            monkeypatch, CapabilityLevel.ACE, CapabilityLevel.ACE
        )
        assert outcome.unpatched_matches is True

    async def test_stronger_than_claim_passes(self, monkeypatch):
        outcome = await _run_simulated_verdict(
            monkeypatch, CapabilityLevel.ACE, CapabilityLevel.LPE
        )
        assert outcome.unpatched_matches is True

    async def test_nothing_verified_fails(self, monkeypatch):
        outcome = await _run_simulated_verdict(
            monkeypatch, CapabilityLevel.ACE, None
        )
        assert outcome.unpatched_matches is False
