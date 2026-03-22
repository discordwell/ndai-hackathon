"""Tests for the capability-oracle verification protocol."""

from unittest.mock import MagicMock

import pytest

from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    CapabilityLevel,
    CapabilityResult,
    ClaimedCapability,
    FileReplacement,
    PinnedPackage,
    PoCResult,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)
from ndai.enclave.vuln_verify.oracles import OracleManager
from ndai.enclave.vuln_verify.poc_executor import PoCExecutor, ServiceStatus
from ndai.enclave.vuln_verify.protocol import VulnVerificationProtocol


def _make_spec(capability=CapabilityLevel.ACE, runs=1):
    return TargetSpec(
        spec_id="test-spec",
        base_image="ubuntu:22.04",
        packages=[PinnedPackage("apache2", "2.4.52-1")],
        config_files=[],
        services=[ServiceSpec("apache2", "service apache2 start", "true")],
        poc=PoCSpec("bash", "curl http://localhost/"),
        claimed_capability=ClaimedCapability(level=capability, reliability_runs=runs),
        service_user="www-data",
    )


def _mock_executor(poc_result):
    executor = MagicMock(spec=PoCExecutor)
    executor.start_services.return_value = [
        ServiceStatus(name="apache2", started=True, healthy=True)
    ]
    executor.execute_poc.return_value = poc_result
    return executor


def _mock_oracle(ace=False, lpe=False, info=False, callback=False, crash=False, dos=False):
    oracle = MagicMock(spec=OracleManager)

    verified = None
    if lpe:
        verified = CapabilityLevel.LPE
    elif callback:
        verified = CapabilityLevel.CALLBACK
    elif ace:
        verified = CapabilityLevel.ACE
    elif info:
        verified = CapabilityLevel.INFO_LEAK
    elif dos:
        verified = CapabilityLevel.DOS
    elif crash:
        verified = CapabilityLevel.CRASH

    oracle.check_result.return_value = CapabilityResult(
        claimed=CapabilityLevel.ACE,
        verified_level=verified,
        ace_canary_found=ace,
        lpe_canary_found=lpe,
        info_canary_found=info,
        callback_received=callback,
        crash_detected=crash,
        dos_detected=dos,
    )
    return oracle


class TestProtocolACE:
    def test_ace_verified(self):
        poc_result = PoCResult(0, "canary_value_here", "", None, False, 1.0)
        executor = _mock_executor(poc_result)
        oracle = _mock_oracle(ace=True)

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.ACE),
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.unpatched_capability.verified_level == CapabilityLevel.ACE
        assert result.unpatched_capability.ace_canary_found is True
        assert result.unpatched_capability.reliability_score == 1.0

    def test_ace_claimed_but_only_crash(self):
        poc_result = PoCResult(139, "", "segfault", 11, False, 0.5)
        executor = _mock_executor(poc_result)
        oracle = _mock_oracle(crash=True)  # Only crash detected, no ACE

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.ACE),
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.unpatched_capability.verified_level == CapabilityLevel.CRASH
        assert result.unpatched_capability.ace_canary_found is False

    def test_nothing_verified(self):
        poc_result = PoCResult(0, "clean", "", None, False, 1.0)
        executor = _mock_executor(poc_result)
        oracle = _mock_oracle()  # Nothing detected

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.ACE),
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.unpatched_capability.verified_level is None


class TestProtocolLPE:
    def test_lpe_verified(self):
        poc_result = PoCResult(0, "root_canary", "", None, False, 1.0)
        executor = _mock_executor(poc_result)
        oracle = _mock_oracle(ace=True, lpe=True)

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.LPE),
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.unpatched_capability.verified_level == CapabilityLevel.LPE


class TestProtocolWithOverlay:
    def test_no_overlap(self):
        """Exploit works unpatched, fails on patched."""
        poc_result = PoCResult(0, "canary", "", None, False, 1.0)
        executor = _mock_executor(poc_result)

        # First call: ACE on unpatched. Second call: nothing on patched
        ace_result = CapabilityResult(
            claimed=CapabilityLevel.ACE, verified_level=CapabilityLevel.ACE,
            ace_canary_found=True, reliability_score=1.0,
        )
        nothing_result = CapabilityResult(
            claimed=CapabilityLevel.ACE, verified_level=None,
        )
        oracle = MagicMock(spec=OracleManager)
        oracle.check_result.side_effect = [ace_result, nothing_result]

        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/test.so", b"patched")],
        )
        overlay_handler = MagicMock()

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.ACE),
            overlay=overlay,
            overlay_handler=overlay_handler,
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.unpatched_capability.verified_level == CapabilityLevel.ACE
        assert result.patched_capability.verified_level is None
        assert result.overlap_detected is False

    def test_overlap_detected(self):
        """Exploit works on BOTH — buyer's patches don't block it."""
        ace_result = CapabilityResult(
            claimed=CapabilityLevel.ACE, verified_level=CapabilityLevel.ACE,
            ace_canary_found=True,
        )
        oracle = MagicMock(spec=OracleManager)
        oracle.check_result.return_value = ace_result

        poc_result = PoCResult(0, "canary", "", None, False, 1.0)
        executor = _mock_executor(poc_result)

        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/test.so", b"patched")],
        )

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.ACE),
            overlay=overlay,
            overlay_handler=MagicMock(),
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.overlap_detected is True


class TestReliability:
    def test_multiple_runs(self):
        """3 runs, 2 succeed → reliability 0.67."""
        poc_result = PoCResult(0, "canary", "", None, False, 1.0)
        executor = _mock_executor(poc_result)

        ace_result = CapabilityResult(
            claimed=CapabilityLevel.ACE, verified_level=CapabilityLevel.ACE,
            ace_canary_found=True,
        )
        fail_result = CapabilityResult(
            claimed=CapabilityLevel.ACE, verified_level=None,
        )

        oracle = MagicMock(spec=OracleManager)
        oracle.check_result.side_effect = [ace_result, fail_result, ace_result]

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.ACE, runs=3),
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.unpatched_capability.reliability_score == pytest.approx(0.67, abs=0.01)
        assert result.unpatched_capability.reliability_runs == 3
        assert result.unpatched_capability.verified_level == CapabilityLevel.ACE

    def test_all_fail(self):
        poc_result = PoCResult(0, "no canary", "", None, False, 1.0)
        executor = _mock_executor(poc_result)

        fail_result = CapabilityResult(
            claimed=CapabilityLevel.ACE, verified_level=None,
        )
        oracle = MagicMock(spec=OracleManager)
        oracle.check_result.return_value = fail_result

        protocol = VulnVerificationProtocol(
            spec=_make_spec(CapabilityLevel.ACE, runs=3),
            executor=executor,
            oracle=oracle,
        )
        result = protocol.run()

        assert result.unpatched_capability.reliability_score == 0.0
        assert result.unpatched_capability.verified_level is None


class TestVerificationChain:
    def test_chain_hash_present(self):
        poc_result = PoCResult(0, "canary", "", None, False, 1.0)
        executor = _mock_executor(poc_result)
        oracle = _mock_oracle(ace=True)

        protocol = VulnVerificationProtocol(
            spec=_make_spec(), executor=executor, oracle=oracle,
        )
        result = protocol.run()

        assert len(result.verification_chain_hash) == 64  # SHA-256 hex

    def test_services_stopped_after(self):
        poc_result = PoCResult(0, "", "", None, False, 1.0)
        executor = _mock_executor(poc_result)
        oracle = _mock_oracle()

        protocol = VulnVerificationProtocol(
            spec=_make_spec(), executor=executor, oracle=oracle,
        )
        protocol.run()

        executor.stop_services.assert_called()
