"""Tests for the EIF builder."""

import pytest

from ndai.enclave.vuln_verify.builder import BuildError, EIFBuilder
from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    ClaimedCapability,
    ConfigFile,
    PinnedPackage,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)


def _make_spec(**overrides):
    defaults = dict(
        spec_id="test-spec",
        base_image="ubuntu:22.04",
        packages=[
            PinnedPackage("apache2", "2.4.52-1ubuntu4.3"),
            PinnedPackage("libssl1.1", "1.1.1f-1ubuntu2.20"),
        ],
        config_files=[
            ConfigFile("/etc/apache2/ports.conf", "Listen 80\nListen 443"),
        ],
        services=[ServiceSpec("apache2", "service apache2 start", "curl -sf http://localhost/ > /dev/null")],
        poc=PoCSpec("bash", "curl http://localhost/ -H 'Evil: test'"),
        claimed_capability=ClaimedCapability(level=CapabilityLevel.ACE),
    )
    defaults.update(overrides)
    return TargetSpec(**defaults)


class TestGenerateDockerfile:
    def setup_method(self):
        self.builder = EIFBuilder()

    def test_contains_base_image(self):
        spec = _make_spec(base_image="debian:12")
        df = self.builder.generate_dockerfile(spec)
        assert "FROM debian:12 AS target" in df

    def test_contains_packages(self):
        spec = _make_spec()
        df = self.builder.generate_dockerfile(spec)
        assert "apache2=2.4.52-1ubuntu4.3" in df
        assert "libssl1.1=1.1.1f-1ubuntu2.20" in df

    def test_contains_config_copies(self):
        spec = _make_spec()
        df = self.builder.generate_dockerfile(spec)
        assert "COPY configs/etc/apache2/ports.conf /etc/apache2/ports.conf" in df

    def test_contains_python_install(self):
        spec = _make_spec()
        df = self.builder.generate_dockerfile(spec)
        assert "python3" in df
        assert "python3.11-pip" in df or "pip3 install" in df

    def test_contains_users(self):
        spec = _make_spec()
        df = self.builder.generate_dockerfile(spec)
        assert "useradd" in df
        assert "enclave" in df
        assert "poc" in df

    def test_contains_entrypoint(self):
        spec = _make_spec()
        df = self.builder.generate_dockerfile(spec)
        assert "ndai.enclave.app" in df

    def test_empty_packages(self):
        spec = _make_spec(packages=[])
        df = self.builder.generate_dockerfile(spec)
        assert "No packages to install" in df

    def test_empty_config(self):
        spec = _make_spec(config_files=[])
        df = self.builder.generate_dockerfile(spec)
        assert "No config files" in df


class TestSpecHash:
    def setup_method(self):
        self.builder = EIFBuilder()

    def test_deterministic(self):
        spec = _make_spec()
        h1 = self.builder.spec_hash(spec)
        h2 = self.builder.spec_hash(spec)
        assert h1 == h2

    def test_different_packages_different_hash(self):
        spec1 = _make_spec(packages=[PinnedPackage("a", "1.0")])
        spec2 = _make_spec(packages=[PinnedPackage("b", "1.0")])
        assert self.builder.spec_hash(spec1) != self.builder.spec_hash(spec2)

    def test_different_base_image_different_hash(self):
        spec1 = _make_spec(base_image="ubuntu:22.04")
        spec2 = _make_spec(base_image="debian:12")
        assert self.builder.spec_hash(spec1) != self.builder.spec_hash(spec2)

    def test_hash_length(self):
        spec = _make_spec()
        assert len(self.builder.spec_hash(spec)) == 16


class TestBuildValidation:
    @pytest.mark.asyncio
    async def test_invalid_spec_raises(self):
        builder = EIFBuilder()
        spec = _make_spec(base_image="malicious:latest")
        with pytest.raises(BuildError, match="validation failed"):
            await builder.build_eif(spec)
