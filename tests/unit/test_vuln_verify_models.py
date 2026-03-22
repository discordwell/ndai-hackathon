"""Tests for PoC verification data models."""

import pytest

from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    ConfigFile,
    EIFManifest,
    ExpectedOutcome,
    FileReplacement,
    MAX_OUTPUT_BYTES,
    PinnedPackage,
    PoCResult,
    PoCSpec,
    ResourceLimits,
    ServiceSpec,
    TargetSpec,
    VerificationResult,
)


class TestTargetSpec:
    def _make_spec(self, **overrides):
        defaults = dict(
            spec_id="test-spec-1",
            base_image="ubuntu:22.04",
            packages=[PinnedPackage("apache2", "2.4.52-1ubuntu4.3")],
            config_files=[ConfigFile("/etc/apache2/ports.conf", "Listen 80")],
            services=[ServiceSpec("apache2", "service apache2 start", "curl -sf http://localhost/ > /dev/null")],
            poc=PoCSpec("bash", "curl -s http://localhost/ -H 'X-Evil: test'"),
            expected_outcome=ExpectedOutcome(crash_signal=11),
        )
        defaults.update(overrides)
        return TargetSpec(**defaults)

    def test_construction(self):
        spec = self._make_spec()
        assert spec.base_image == "ubuntu:22.04"
        assert len(spec.packages) == 1
        assert spec.packages[0].name == "apache2"

    def test_frozen(self):
        spec = self._make_spec()
        with pytest.raises(AttributeError):
            spec.base_image = "debian:12"

    def test_empty_packages(self):
        spec = self._make_spec(packages=[])
        assert len(spec.packages) == 0


class TestBuyerOverlay:
    def test_construction(self):
        overlay = BuyerOverlay(
            overlay_id="overlay-1",
            file_replacements=[
                FileReplacement("/usr/lib/libapr-1.so.0", b"\x7fELF..."),
            ],
            pre_apply_commands=["service apache2 stop"],
            post_apply_commands=["service apache2 start"],
        )
        assert len(overlay.file_replacements) == 1
        assert overlay.file_replacements[0].path == "/usr/lib/libapr-1.so.0"

    def test_empty_overlay(self):
        overlay = BuyerOverlay(overlay_id="empty", file_replacements=[])
        assert len(overlay.pre_apply_commands) == 0


class TestPoCResult:
    def test_construction(self):
        result = PoCResult(
            exit_code=139, stdout="", stderr="Segmentation fault",
            signal=11, timed_out=False, duration_sec=0.5,
        )
        assert result.signal == 11
        assert result.exit_code == 139

    def test_frozen(self):
        result = PoCResult(0, "", "", None, False, 1.0)
        with pytest.raises(AttributeError):
            result.exit_code = 1


class TestVerificationResult:
    def test_no_overlay(self):
        result = VerificationResult(
            spec_id="s1",
            unpatched_result=PoCResult(139, "", "segfault", 11, False, 0.5),
            unpatched_matches_expected=True,
            patched_result=None,
            patched_matches_expected=None,
            overlap_detected=None,
            verification_chain_hash="abc123",
            timestamp="2026-03-22T00:00:00Z",
        )
        assert result.overlap_detected is None

    def test_with_overlay_no_overlap(self):
        result = VerificationResult(
            spec_id="s1",
            unpatched_result=PoCResult(139, "", "segfault", 11, False, 0.5),
            unpatched_matches_expected=True,
            patched_result=PoCResult(0, "OK", "", None, False, 0.3),
            patched_matches_expected=False,
            overlap_detected=False,
            verification_chain_hash="abc123",
            timestamp="2026-03-22T00:00:00Z",
        )
        assert result.overlap_detected is False

    def test_with_overlay_overlap(self):
        """If PoC works on BOTH unpatched and patched, it's a new 0day (no overlap)."""
        result = VerificationResult(
            spec_id="s1",
            unpatched_result=PoCResult(139, "", "segfault", 11, False, 0.5),
            unpatched_matches_expected=True,
            patched_result=PoCResult(139, "", "segfault", 11, False, 0.5),
            patched_matches_expected=True,
            overlap_detected=True,
            verification_chain_hash="abc123",
            timestamp="2026-03-22T00:00:00Z",
        )
        assert result.overlap_detected is True


class TestResourceLimits:
    def test_defaults(self):
        limits = ResourceLimits()
        assert limits.max_cpu_sec == 60
        assert limits.max_memory_mb == 512
        assert limits.max_wall_sec == 120
        assert limits.max_output_bytes == MAX_OUTPUT_BYTES

    def test_custom(self):
        limits = ResourceLimits(max_cpu_sec=30, max_memory_mb=256)
        assert limits.max_cpu_sec == 30


class TestEIFManifest:
    def test_construction(self):
        manifest = EIFManifest(
            spec_id="s1", eif_path="/opt/eifs/s1.eif",
            pcr0="aaa", pcr1="bbb", pcr2="ccc",
            base_image="ubuntu:22.04", package_count=3,
            docker_image_hash="sha256:abc", built_at="2026-03-22T00:00:00Z",
        )
        assert manifest.pcr0 == "aaa"
