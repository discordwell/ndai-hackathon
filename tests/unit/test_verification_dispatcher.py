"""Unit tests for verification dispatcher, nitro verifier, and browser executor."""

import uuid

import pytest

from ndai.models.known_target import KnownTarget
from ndai.models.verification_proposal import VerificationProposal
from ndai.services.verification_dispatcher import VerificationDispatcher, VerificationOutcome
from ndai.services.nitro_verifier import NitroVerifier
from ndai.enclave.vuln_verify.browser_executor import BrowserPoCServer


# ── Dispatcher routing ──


class TestVerificationDispatcher:
    @pytest.fixture
    def dispatcher(self):
        return VerificationDispatcher()

    def _make_target(self, **kwargs):
        defaults = dict(
            slug="test-target",
            display_name="Test Target",
            platform="linux",
            current_version="1.0.0",
            verification_method="nitro",
            poc_script_type="bash",
            poc_instructions="Test",
            escrow_amount_usd=100,
        )
        defaults.update(kwargs)
        return KnownTarget(**defaults)

    def _make_proposal(self, **kwargs):
        defaults = dict(
            seller_pubkey="a" * 64,
            target_id=uuid.uuid4(),
            target_version="1.0.0",
            poc_script="#!/bin/bash\nid",
            poc_script_type="bash",
            claimed_capability="ace",
            asking_price_eth=5.0,
            status="queued",
            deposit_required=False,
        )
        defaults.update(kwargs)
        return VerificationProposal(**defaults)

    @pytest.mark.asyncio
    async def test_dispatch_manual_method(self, dispatcher):
        target = self._make_target(verification_method="manual")
        proposal = self._make_proposal()
        result = await dispatcher.dispatch(proposal, target)
        assert result.status == "manual_review"
        assert result.success is False

    @pytest.mark.asyncio
    async def test_dispatch_unknown_method(self, dispatcher):
        target = self._make_target(verification_method="quantum")
        proposal = self._make_proposal()
        result = await dispatcher.dispatch(proposal, target)
        assert result.status == "error"
        assert "Unknown" in result.error

    @pytest.mark.asyncio
    async def test_dispatch_ios_uses_stub(self, dispatcher):
        target = self._make_target(
            verification_method="corellium",
            platform="ios",
            escrow_amount_usd=500,
        )
        proposal = self._make_proposal()
        result = await dispatcher.dispatch(proposal, target)
        assert result.status == "manual_review"

    def test_register_custom_backend(self, dispatcher):
        class FakeBackend:
            async def verify(self, proposal, target, callback=None):
                return VerificationOutcome(success=True, status="passed")

        dispatcher.register_backend("nitro", FakeBackend())
        assert "nitro" in dispatcher._backends


# ── Nitro Verifier (TargetSpec construction) ──


class TestNitroVerifier:
    def test_build_target_spec_from_known_target(self):
        verifier = NitroVerifier()
        target = KnownTarget(
            slug="ubuntu-lts",
            display_name="Ubuntu Server LTS",
            platform="linux",
            current_version="24.04",
            verification_method="nitro",
            base_image="ubuntu:24.04",
            packages_json=[
                {"name": "openssh-server", "version": "1:9.6p1-3ubuntu13"},
                {"name": "apache2", "version": "2.4.58-1ubuntu8"},
            ],
            services_json=[
                {"name": "sshd", "start_command": "service ssh start", "health_check": "service ssh status", "timeout_sec": 10},
            ],
            config_files_json=None,
            build_steps_json=None,
            service_user="www-data",
            poc_script_type="bash",
            poc_instructions="Test",
        )
        proposal = VerificationProposal(
            id=uuid.uuid4(),
            seller_pubkey="b" * 64,
            target_id=uuid.uuid4(),
            target_version="24.04",
            poc_script="#!/bin/bash\ncat /root/canary_lpe",
            poc_script_type="bash",
            claimed_capability="lpe",
            reliability_runs=5,
            asking_price_eth=10.0,
            status="queued",
            deposit_required=False,
        )

        spec = verifier.build_target_spec(target, proposal)
        assert spec.base_image == "ubuntu:24.04"
        assert len(spec.packages) == 2
        assert spec.packages[0].name == "openssh-server"
        assert len(spec.services) == 1
        assert spec.poc.script_type == "bash"
        assert spec.poc.script_content == "#!/bin/bash\ncat /root/canary_lpe"
        assert spec.claimed_capability.level.value == "lpe"
        assert spec.claimed_capability.reliability_runs == 5
        assert spec.service_user == "www-data"

    def test_build_target_spec_browser_target(self):
        verifier = NitroVerifier()
        target = KnownTarget(
            slug="chrome-linux",
            display_name="Google Chrome (Linux)",
            platform="linux",
            current_version="124.0",
            verification_method="nitro",
            base_image="ubuntu:22.04",
            packages_json=[{"name": "chromium-browser", "version": "124.0"}],
            services_json=[{
                "name": "chromium",
                "start_command": "chromium-browser --headless",
                "health_check": "true",
            }],
            poc_script_type="html",
            poc_instructions="Test",
        )
        proposal = VerificationProposal(
            id=uuid.uuid4(),
            seller_pubkey="c" * 64,
            target_id=uuid.uuid4(),
            target_version="124.0",
            poc_script="<html><script>document.write('pwned')</script></html>",
            poc_script_type="html",
            claimed_capability="ace",
            asking_price_eth=50.0,
            status="queued",
            deposit_required=False,
        )

        spec = verifier.build_target_spec(target, proposal)
        assert spec.poc.script_type == "html"
        assert "<html>" in spec.poc.script_content

    def test_build_target_spec_no_packages(self):
        verifier = NitroVerifier()
        target = KnownTarget(
            slug="bare",
            display_name="Bare",
            platform="linux",
            current_version="1.0",
            verification_method="nitro",
            base_image="ubuntu:22.04",
            packages_json=None,
            services_json=None,
            poc_script_type="bash",
            poc_instructions="Test",
        )
        proposal = VerificationProposal(
            id=uuid.uuid4(),
            seller_pubkey="d" * 64,
            target_id=uuid.uuid4(),
            target_version="1.0",
            poc_script="echo test",
            poc_script_type="bash",
            claimed_capability="crash",
            asking_price_eth=1.0,
            status="queued",
            deposit_required=False,
        )

        spec = verifier.build_target_spec(target, proposal)
        assert len(spec.packages) == 0
        assert len(spec.services) == 0


# ── Browser executor ──


class TestBrowserPoCServer:
    def test_server_starts_and_stops(self):
        server = BrowserPoCServer("<html>test</html>", port=18080)
        port = server.start()
        assert port == 18080
        server.stop()

    def test_server_serves_html(self):
        import urllib.request
        server = BrowserPoCServer("<html><body>exploit</body></html>", port=18082)
        try:
            port = server.start()
            response = urllib.request.urlopen(f"http://localhost:{port}/poc.html")
            content = response.read().decode()
            assert "exploit" in content
        finally:
            server.stop()


# ── VerificationOutcome ──


class TestVerificationOutcome:
    def test_success_outcome(self):
        outcome = VerificationOutcome(
            success=True,
            capability_result={"claimed": "ace", "verified_level": "ace"},
            chain_hash="abc123",
            pcr0="def456",
            status="passed",
        )
        assert outcome.success is True
        assert outcome.status == "passed"

    def test_failure_outcome(self):
        outcome = VerificationOutcome(
            success=False,
            status="failed",
            error="PoC did not achieve claimed capability",
        )
        assert outcome.success is False

    def test_manual_review_outcome(self):
        outcome = VerificationOutcome(
            success=False,
            status="manual_review",
        )
        assert outcome.status == "manual_review"
