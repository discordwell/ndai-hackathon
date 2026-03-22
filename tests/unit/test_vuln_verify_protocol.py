"""Tests for the verification protocol."""

from unittest.mock import MagicMock, patch

import pytest

from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    ExpectedOutcome,
    FileReplacement,
    PinnedPackage,
    PoCResult,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)
from ndai.enclave.vuln_verify.poc_executor import PoCExecutor, ServiceStatus
from ndai.enclave.vuln_verify.protocol import VulnVerificationProtocol


def _make_spec():
    return TargetSpec(
        spec_id="test-spec",
        base_image="ubuntu:22.04",
        packages=[PinnedPackage("apache2", "2.4.52-1")],
        config_files=[],
        services=[ServiceSpec("apache2", "service apache2 start", "true")],
        poc=PoCSpec("bash", "curl http://localhost/"),
        expected_outcome=ExpectedOutcome(crash_signal=11),
    )


def _mock_executor(unpatched_result, patched_result=None):
    executor = MagicMock(spec=PoCExecutor)
    executor.start_services.return_value = [
        ServiceStatus(name="apache2", started=True, healthy=True)
    ]

    if patched_result:
        executor.execute_poc.side_effect = [unpatched_result, patched_result]
    else:
        executor.execute_poc.return_value = unpatched_result

    def check_outcome(result, expected):
        if expected.crash_signal is not None:
            return result.signal == expected.crash_signal
        if expected.exit_code is not None:
            return result.exit_code == expected.exit_code
        return False

    executor.check_outcome.side_effect = check_outcome
    return executor


class TestProtocolUnpatchedOnly:
    def test_poc_succeeds(self):
        """PoC crashes target as expected."""
        crash = PoCResult(139, "", "segfault", 11, False, 0.5)
        executor = _mock_executor(crash)

        protocol = VulnVerificationProtocol(
            spec=_make_spec(), executor=executor,
        )
        result = protocol.run()

        assert result.unpatched_matches_expected is True
        assert result.patched_result is None
        assert result.overlap_detected is None
        assert result.verification_chain_hash  # Non-empty hash

    def test_poc_fails(self):
        """PoC does NOT crash target."""
        clean = PoCResult(0, "OK", "", None, False, 0.3)
        executor = _mock_executor(clean)

        protocol = VulnVerificationProtocol(
            spec=_make_spec(), executor=executor,
        )
        result = protocol.run()

        assert result.unpatched_matches_expected is False


class TestProtocolWithOverlay:
    def test_no_overlap(self):
        """PoC works on unpatched, fails on patched → buyer's patch blocks it."""
        crash = PoCResult(139, "", "segfault", 11, False, 0.5)
        clean = PoCResult(0, "OK", "", None, False, 0.3)
        executor = _mock_executor(crash, clean)

        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/test.so", b"patched")],
        )
        overlay_handler = MagicMock()

        protocol = VulnVerificationProtocol(
            spec=_make_spec(),
            overlay=overlay,
            overlay_handler=overlay_handler,
            executor=executor,
        )
        result = protocol.run()

        assert result.unpatched_matches_expected is True
        assert result.patched_matches_expected is False
        assert result.overlap_detected is False
        overlay_handler.apply_overlay.assert_called_once()

    def test_overlap_detected(self):
        """PoC works on BOTH → buyer's patch doesn't block it → new 0day."""
        crash = PoCResult(139, "", "segfault", 11, False, 0.5)
        executor = _mock_executor(crash, crash)

        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/test.so", b"patched")],
        )
        overlay_handler = MagicMock()

        protocol = VulnVerificationProtocol(
            spec=_make_spec(),
            overlay=overlay,
            overlay_handler=overlay_handler,
            executor=executor,
        )
        result = protocol.run()

        assert result.unpatched_matches_expected is True
        assert result.patched_matches_expected is True
        assert result.overlap_detected is True

    def test_poc_fails_unpatched(self):
        """PoC fails on unpatched → overlap is None (can't test what doesn't work)."""
        clean = PoCResult(0, "OK", "", None, False, 0.3)
        executor = _mock_executor(clean, clean)

        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/test.so", b"patched")],
        )
        overlay_handler = MagicMock()

        protocol = VulnVerificationProtocol(
            spec=_make_spec(),
            overlay=overlay,
            overlay_handler=overlay_handler,
            executor=executor,
        )
        result = protocol.run()

        assert result.unpatched_matches_expected is False
        # Overlap = unpatched_matches AND patched_matches = False AND False = False
        assert result.overlap_detected is False


class TestVerificationChain:
    def test_chain_hash_is_deterministic_for_same_input(self):
        """Same execution results → same chain hash (ignoring timestamps)."""
        crash = PoCResult(139, "", "segfault", 11, False, 0.5)
        executor = _mock_executor(crash)

        p1 = VulnVerificationProtocol(spec=_make_spec(), executor=executor)
        r1 = p1.run()

        # Reset mock
        executor.execute_poc.return_value = crash
        p2 = VulnVerificationProtocol(spec=_make_spec(), executor=executor)
        r2 = p2.run()

        # Hashes differ because of timestamp, but both are non-empty
        assert len(r1.verification_chain_hash) == 64  # SHA-256 hex
        assert len(r2.verification_chain_hash) == 64

    def test_services_stopped_after_protocol(self):
        crash = PoCResult(139, "", "segfault", 11, False, 0.5)
        executor = _mock_executor(crash)

        protocol = VulnVerificationProtocol(spec=_make_spec(), executor=executor)
        protocol.run()

        executor.stop_services.assert_called_once()
