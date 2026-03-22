"""EIF builder — generates per-target enclave images from seller TargetSpec.

Parent-side service that:
1. Validates the TargetSpec
2. Generates a Dockerfile from the spec
3. Builds the Docker image
4. Converts to EIF via nitro-cli (when available)
5. Returns PCR manifest
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ndai.enclave.vuln_verify.models import (
    ConfigFile,
    EIFManifest,
    PinnedPackage,
    ServiceSpec,
    TargetSpec,
)
from ndai.enclave.vuln_verify.security import validate_target_spec

logger = logging.getLogger(__name__)

# Path to the NDAI source for copying into the enclave image
_NDAI_ROOT = Path(__file__).resolve().parents[3]


class BuildError(Exception):
    """Error during EIF build."""


class EIFBuilder:
    """Builds per-target EIF images from seller TargetSpec."""

    def __init__(
        self,
        build_dir: str = "/tmp/ndai-eif-builds",
        eif_store_dir: str = "/opt/ndai/eifs",
    ):
        self._build_dir = Path(build_dir)
        self._eif_store_dir = Path(eif_store_dir)

    def generate_dockerfile(self, spec: TargetSpec) -> str:
        """Generate a Dockerfile from the target specification."""
        package_install = self._render_package_install(spec.packages)
        config_copies = self._render_config_copies(spec.config_files)
        build_steps = self._render_build_steps(spec.build_steps)
        service_setup = self._render_service_setup(spec.services)

        return f"""# Auto-generated per-target EIF for spec {spec.spec_id}
# Base: {spec.base_image}
# Packages: {len(spec.packages)}

FROM {spec.base_image} AS target

# Install target software with pinned versions
{package_install}

# Apply configuration files
{config_copies}

# Custom build steps
{build_steps}

# Service setup
{service_setup}

# --- Enclave runtime layer ---
FROM target AS enclave

# Install Python runtime for NDAI enclave app
RUN apt-get update && apt-get install -y --no-install-recommends \\
    python3 python3-pip python3-venv ca-certificates curl \\
    && rm -rf /var/lib/apt/lists/*

# Install NDAI enclave runtime
COPY requirements-enclave.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements-enclave.txt \\
    && rm /tmp/requirements-enclave.txt

# Copy NDAI source
COPY ndai/ /app/ndai/

# Create non-root users
RUN useradd --system --no-create-home enclave && \\
    useradd --system --no-create-home poc

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

ENTRYPOINT ["python3", "-m", "ndai.enclave.app"]
"""

    def spec_hash(self, spec: TargetSpec) -> str:
        """Compute a deterministic hash of a TargetSpec for caching."""
        canonical = json.dumps({
            "base_image": spec.base_image,
            "packages": [(p.name, p.version) for p in spec.packages],
            "config_files": [(c.path, hashlib.sha256(c.content.encode()).hexdigest()) for c in spec.config_files],
            "build_steps": spec.build_steps,
            "services": [(s.name, s.start_command) for s in spec.services],
        }, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    async def build_eif(self, spec: TargetSpec) -> EIFManifest:
        """Full pipeline: validate -> generate Dockerfile -> docker build -> nitro-cli -> PCR manifest."""
        # Validate
        errors = validate_target_spec(spec)
        if errors:
            raise BuildError(f"Target spec validation failed: {'; '.join(errors)}")

        # Check cache
        cache_key = self.spec_hash(spec)
        cached_eif = self._eif_store_dir / f"{cache_key}.eif"
        cached_manifest = self._eif_store_dir / f"{cache_key}.json"
        if cached_manifest.exists():
            with cached_manifest.open() as f:
                data = json.load(f)
            logger.info("Using cached EIF for spec %s: %s", spec.spec_id, cache_key)
            return EIFManifest(**data)

        # Build in temp directory
        build_context = self._build_dir / cache_key
        build_context.mkdir(parents=True, exist_ok=True)

        try:
            # Generate Dockerfile
            dockerfile_content = self.generate_dockerfile(spec)
            (build_context / "Dockerfile").write_text(dockerfile_content)

            # Write config files to build context
            for cf in spec.config_files:
                cf_dir = build_context / "configs" / cf.path.lstrip("/")
                cf_dir.parent.mkdir(parents=True, exist_ok=True)
                cf_dir.write_text(cf.content)

            # Write requirements
            self._write_requirements(build_context)

            # Copy NDAI source
            ndai_src = _NDAI_ROOT / "ndai"
            if ndai_src.exists():
                dest = build_context / "ndai"
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(ndai_src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

            # Docker build
            image_tag = f"ndai-vuln-{cache_key}"
            docker_hash = await self._docker_build(str(build_context), image_tag)

            # Convert to EIF (if nitro-cli available)
            eif_path = str(cached_eif)
            pcrs = await self._nitro_convert(image_tag, eif_path)

            manifest = EIFManifest(
                spec_id=spec.spec_id,
                eif_path=eif_path,
                pcr0=pcrs.get("PCR0", "simulated"),
                pcr1=pcrs.get("PCR1", "simulated"),
                pcr2=pcrs.get("PCR2", "simulated"),
                base_image=spec.base_image,
                package_count=len(spec.packages),
                docker_image_hash=docker_hash,
                built_at=datetime.now(timezone.utc).isoformat(),
            )

            # Cache manifest
            self._eif_store_dir.mkdir(parents=True, exist_ok=True)
            with cached_manifest.open("w") as f:
                json.dump({
                    "spec_id": manifest.spec_id,
                    "eif_path": manifest.eif_path,
                    "pcr0": manifest.pcr0,
                    "pcr1": manifest.pcr1,
                    "pcr2": manifest.pcr2,
                    "base_image": manifest.base_image,
                    "package_count": manifest.package_count,
                    "docker_image_hash": manifest.docker_image_hash,
                    "built_at": manifest.built_at,
                }, f)

            logger.info("Built EIF for spec %s: pcr0=%s", spec.spec_id, manifest.pcr0[:16])
            return manifest

        finally:
            # Clean up build context (keep cached artifacts)
            if build_context.exists():
                shutil.rmtree(build_context, ignore_errors=True)

    def _render_package_install(self, packages: list[PinnedPackage]) -> str:
        if not packages:
            return "# No packages to install"
        lines = " \\\n    ".join(f"{p.name}={p.version}" for p in packages)
        return (
            f"RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
            f"    {lines} \\\n"
            f"    && rm -rf /var/lib/apt/lists/*"
        )

    def _render_config_copies(self, configs: list[ConfigFile]) -> str:
        if not configs:
            return "# No config files"
        lines = []
        for cf in configs:
            src = f"configs{cf.path}"
            lines.append(f"COPY {src} {cf.path}")
        return "\n".join(lines)

    def _render_build_steps(self, steps: list[str]) -> str:
        if not steps:
            return "# No custom build steps"
        lines = []
        for step in steps:
            lines.append(f"RUN {step}")
        return "\n".join(lines)

    def _render_service_setup(self, services: list[ServiceSpec]) -> str:
        if not services:
            return "# No services"
        return "# Services will be started at runtime by the enclave app"

    def _write_requirements(self, build_context: Path) -> None:
        """Write minimal Python requirements for the enclave runtime."""
        reqs = [
            "anthropic>=0.42.0",
            "openai>=1.0.0",
            "cryptography>=44.0.0",
            "cbor2>=5.6.0",
            "httpx>=0.28.0",
        ]
        (build_context / "requirements-enclave.txt").write_text("\n".join(reqs) + "\n")

    async def _docker_build(self, context_dir: str, tag: str) -> str:
        """Run docker build, return image hash."""
        cmd = ["docker", "build", "-t", tag, "-q", context_dir]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise BuildError(f"Docker build failed: {stderr.decode()[:500]}")

        image_hash = stdout.decode().strip()
        logger.info("Docker build complete: %s -> %s", tag, image_hash[:20])
        return image_hash

    async def _nitro_convert(self, docker_image: str, output_path: str) -> dict[str, str]:
        """Run nitro-cli build-enclave, return PCR values."""
        if not shutil.which("nitro-cli"):
            logger.warning("nitro-cli not available, returning simulated PCRs")
            # Generate deterministic simulated PCRs from the image tag
            h = hashlib.sha384(docker_image.encode()).hexdigest()
            return {"PCR0": h, "PCR1": h, "PCR2": h}

        cmd = [
            "nitro-cli", "build-enclave",
            "--docker-uri", docker_image,
            "--output-file", output_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise BuildError(f"nitro-cli build failed: {stderr.decode()[:500]}")

        # Parse PCR values from nitro-cli output (JSON)
        try:
            output = json.loads(stdout.decode())
            return {
                "PCR0": output["Measurements"]["PCR0"],
                "PCR1": output["Measurements"]["PCR1"],
                "PCR2": output["Measurements"]["PCR2"],
            }
        except (json.JSONDecodeError, KeyError) as exc:
            raise BuildError(f"Failed to parse nitro-cli output: {exc}") from exc
