"""Tests for the CVE-2024-3094 target specification."""

import pytest

from ndai.enclave.vuln_verify.builder import EIFBuilder
from ndai.enclave.vuln_verify.models import CapabilityLevel
from ndai.enclave.vuln_verify.security import validate_target_spec


class TestXZTargetSpec:
    """Validate the XZ backdoor demo TargetSpec."""

    @pytest.fixture
    def spec(self):
        from demo.target_spec import create_xz_target_spec
        return create_xz_target_spec()

    def test_spec_id(self, spec):
        assert spec.spec_id == "cve-2024-3094-xz-backdoor"

    def test_base_image_whitelisted(self, spec):
        assert spec.base_image == "debian:12"

    def test_packages_present(self, spec):
        pkg_names = [p.name for p in spec.packages]
        assert "openssh-server" in pkg_names
        assert "libssl-dev" in pkg_names
        assert "gcc" in pkg_names

    def test_config_files_include_backdoor_source(self, spec):
        paths = [cf.path for cf in spec.config_files]
        assert "/etc/ndai-build/backdoor_hook.c" in paths
        assert "/etc/ndai-build/test_ed448_public.h" in paths
        assert "/etc/ndai-build/trigger_service.c" in paths

    def test_build_steps_compile_backdoor(self, spec):
        assert any("liblzma_backdoor.so" in step for step in spec.build_steps)
        assert any("trigger_service" in step for step in spec.build_steps)

    def test_service_is_ssh(self, spec):
        assert len(spec.services) == 1
        assert spec.services[0].name == "sshd"

    def test_claimed_capability_is_ace(self, spec):
        assert spec.claimed_capability.level == CapabilityLevel.ACE
        assert spec.claimed_capability.reliability_runs == 3

    def test_poc_is_python3(self, spec):
        assert spec.poc.script_type == "python3"
        assert "poc_trigger" in spec.poc.script_content or "CVE-2024-3094" in spec.poc.script_content

    def test_passes_security_validation(self, spec):
        errors = validate_target_spec(spec)
        assert errors == [], f"Validation failed: {errors}"

    def test_dockerfile_generation(self, spec):
        builder = EIFBuilder()
        dockerfile = builder.generate_dockerfile(spec)
        assert "FROM debian:12" in dockerfile
        assert "openssh-server" in dockerfile
        assert "liblzma_backdoor.so" in dockerfile
        assert "trigger_service" in dockerfile

    def test_spec_hash_deterministic(self, spec):
        builder = EIFBuilder()
        h1 = builder.spec_hash(spec)
        h2 = builder.spec_hash(spec)
        assert h1 == h2
