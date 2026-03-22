"""Tests for the combined demo session (verify → negotiate → seal)."""

from unittest.mock import MagicMock, patch

import pytest

from ndai.enclave.vuln_demo_session import (
    DemoSessionConfig,
    DemoSessionResult,
    VulnDemoSession,
)
from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    CapabilityResult,
    VerificationResult,
)


@pytest.fixture
def mock_vuln_submission():
    from ndai.enclave.agents.base_agent import VulnerabilitySubmission
    return VulnerabilitySubmission(
        target_software="xz-utils",
        target_version="5.6.1",
        vulnerability_class="CWE-506",
        impact_type="RCE",
        affected_component="liblzma",
        cvss_self_assessed=10.0,
        discovery_date="2024-03-29",
        patch_status="unpatched",
        exclusivity="exclusive",
        outside_option_value=0.7,
        max_disclosure_level=3,
        software_category="os_kernel",
    )


@pytest.fixture
def mock_target_spec():
    from demo.target_spec import create_xz_target_spec
    return create_xz_target_spec()


class TestDemoSessionResult:
    def test_success_when_both_present(self):
        from ndai.enclave.negotiation.shelf_life import VulnNegotiationResult, VulnOutcomeType
        result = DemoSessionResult(
            verification=MagicMock(),
            negotiation=VulnNegotiationResult(
                outcome=VulnOutcomeType.AGREEMENT,
                final_price=1.5,
                current_value=0.9,
                disclosure_level=3,
                disclosure_fraction=1.0,
                seller_payoff=1.0,
                buyer_payoff=0.5,
                reason="test",
            ),
        )
        assert result.success

    def test_not_success_when_error(self):
        result = DemoSessionResult(error="something broke")
        assert not result.success

    def test_not_success_when_missing_negotiation(self):
        result = DemoSessionResult(verification=MagicMock())
        assert not result.success


class TestVulnDemoSession:
    def test_skip_verification_goes_to_negotiation(self, mock_target_spec, mock_vuln_submission):
        """When skip_verification=True, session skips to negotiation."""
        config = DemoSessionConfig(
            target_spec=mock_target_spec,
            vulnerability=mock_vuln_submission,
            budget_cap=2.5,
            skip_verification=True,
            skip_sealed_delivery=True,
            llm_provider="openai",
            api_key="test-key",
        )

        progress_events = []

        def capture_progress(event, data):
            progress_events.append(event)

        with patch("ndai.enclave.vuln_demo_session.VulnNegotiationSession") as MockNeg:
            from ndai.enclave.negotiation.shelf_life import VulnNegotiationResult, VulnOutcomeType
            mock_result = VulnNegotiationResult(
                outcome=VulnOutcomeType.AGREEMENT,
                final_price=1.5,
                current_value=0.9,
                disclosure_level=3,
                disclosure_fraction=1.0,
                seller_payoff=1.0,
                buyer_payoff=0.5,
                reason="test",
            )
            MockNeg.return_value.run.return_value = mock_result

            session = VulnDemoSession(config, progress_callback=capture_progress)
            result = session.run()

            assert result.success
            assert result.negotiation.outcome.value == "agreement"
            assert result.negotiation.final_price == 1.5
            assert result.verification is None
            assert "phase_start" in progress_events
            assert "pipeline_complete" in progress_events

    def test_verification_failure_stops_pipeline(self, mock_target_spec, mock_vuln_submission):
        """When verification fails, pipeline stops before negotiation."""
        config = DemoSessionConfig(
            target_spec=mock_target_spec,
            vulnerability=mock_vuln_submission,
            budget_cap=2.5,
            skip_verification=False,
            skip_sealed_delivery=True,
        )

        with patch("ndai.enclave.vuln_demo_session.VulnVerificationProtocol") as MockVerify:
            # Return a verification result with no verified capability
            mock_verify_result = VerificationResult(
                spec_id="test",
                unpatched_capability=CapabilityResult(
                    claimed=CapabilityLevel.ACE,
                    verified_level=None,  # Nothing verified
                ),
                patched_capability=None,
                overlap_detected=None,
                verification_chain_hash="abc123",
                timestamp="2024-03-29T00:00:00Z",
            )
            MockVerify.return_value.run.return_value = mock_verify_result

            session = VulnDemoSession(config)
            result = session.run()

            assert not result.success
            assert "verification failed" in result.error.lower()
            assert result.negotiation is None

    def test_progress_callback_called(self, mock_target_spec, mock_vuln_submission):
        """Progress callback receives events."""
        config = DemoSessionConfig(
            target_spec=mock_target_spec,
            vulnerability=mock_vuln_submission,
            budget_cap=2.5,
            skip_verification=True,
            skip_sealed_delivery=True,
            api_key="test",
        )

        events_received = []

        def on_progress(event, data):
            events_received.append((event, data))

        with patch("ndai.enclave.vuln_demo_session.VulnNegotiationSession") as MockNeg:
            from ndai.enclave.negotiation.shelf_life import VulnNegotiationResult, VulnOutcomeType
            MockNeg.return_value.run.return_value = VulnNegotiationResult(
                outcome=VulnOutcomeType.NO_DEAL,
                final_price=None,
                current_value=0.5,
                disclosure_level=1,
                disclosure_fraction=0.25,
                seller_payoff=None,
                buyer_payoff=None,
                reason="No surplus",
            )

            session = VulnDemoSession(config, progress_callback=on_progress)
            session.run()

        event_names = [e[0] for e in events_received]
        assert "phase_start" in event_names
        assert "phase_complete" in event_names
