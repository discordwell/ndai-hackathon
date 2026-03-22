"""TargetSpec definition for CVE-2024-3094 (XZ Utils Backdoor).

Defines the per-target verification environment that the NDAI enclave
builds to verify the exploit. This spec produces a Docker image with:
  - Debian 12 + OpenSSH server + OpenSSL dev headers + gcc
  - The backdoor hook compiled and installed
  - A trigger service for reliable payload delivery
  - sshd started with LD_PRELOAD=liblzma_backdoor.so
"""

import os

from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    ClaimedCapability,
    ConfigFile,
    PinnedPackage,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)

HERE = os.path.dirname(os.path.abspath(__file__))
XZ_DIR = os.path.join(HERE, "xz_backdoor")


def _read_file(name: str) -> str:
    """Read a file from the xz_backdoor directory."""
    with open(os.path.join(XZ_DIR, name)) as f:
        return f.read()


def create_xz_target_spec() -> TargetSpec:
    """Create the TargetSpec for CVE-2024-3094 verification."""

    # Read the backdoor source files to embed as config files
    backdoor_c = _read_file("backdoor_hook.c")
    pubkey_h = _read_file("test_ed448_public.h")
    trigger_c = _read_file("trigger_service.c")
    entrypoint = _read_file("entrypoint.sh")
    poc_script = _read_file("poc_trigger.py")

    return TargetSpec(
        spec_id="cve-2024-3094-xz-backdoor",
        base_image="debian:12",
        packages=[
            PinnedPackage(name="openssh-server", version="1:9.2p1-2+deb12u3"),
            PinnedPackage(name="libssl-dev", version="3.0.15-1~deb12u1"),
            PinnedPackage(name="gcc", version="4:12.2.0-3"),
            PinnedPackage(name="libc6-dev", version="2.36-9+deb12u9"),
            PinnedPackage(name="python3", version="3.11.2-1+b1"),
            PinnedPackage(name="procps", version="2:4.0.2-3"),
        ],
        config_files=[
            # Backdoor source files (placed in /etc/ndai-build/ for compilation)
            ConfigFile(
                path="/etc/ndai-build/backdoor_hook.c",
                content=backdoor_c,
            ),
            ConfigFile(
                path="/etc/ndai-build/test_ed448_public.h",
                content=pubkey_h,
            ),
            ConfigFile(
                path="/etc/ndai-build/trigger_service.c",
                content=trigger_c,
            ),
            ConfigFile(
                path="/etc/ndai-build/entrypoint.sh",
                content=entrypoint,
                mode=0o755,
            ),
        ],
        build_steps=[
            # Compile the backdoor hook shared library
            "gcc -shared -fPIC -o /usr/lib/liblzma_backdoor.so "
            "/etc/ndai-build/backdoor_hook.c "
            "-I/etc/ndai-build -lssl -lcrypto -ldl -O2",
            # Compile the trigger service
            "gcc -o /usr/local/bin/trigger_service "
            "/etc/ndai-build/trigger_service.c "
            "-lssl -lcrypto -O2",
            # Setup SSH
            "mkdir -p /run/sshd",
            # Create oracle directory
            "mkdir -p /var/lib/ndai-oracle",
            "chmod 755 /var/lib/ndai-oracle",
        ],
        services=[
            ServiceSpec(
                name="sshd",
                start_command="service ssh start",
                health_check="test -f /run/sshd.pid",
                timeout_sec=10,
            ),
        ],
        poc=PoCSpec(
            script_type="python3",
            script_content=poc_script,
            timeout_sec=30,
            run_as_user="poc",
        ),
        claimed_capability=ClaimedCapability(
            level=CapabilityLevel.ACE,
            reliability_runs=3,
        ),
        service_user="sshd",
    )


# Allow running standalone for inspection
if __name__ == "__main__":
    spec = create_xz_target_spec()
    print(f"TargetSpec: {spec.spec_id}")
    print(f"  Base image: {spec.base_image}")
    print(f"  Packages: {len(spec.packages)}")
    print(f"  Config files: {len(spec.config_files)}")
    print(f"  Build steps: {len(spec.build_steps)}")
    print(f"  Services: {len(spec.services)}")
    print(f"  Capability: {spec.claimed_capability.level.value}")
    print(f"  Reliability runs: {spec.claimed_capability.reliability_runs}")

    # Validate
    from ndai.enclave.vuln_verify.security import validate_target_spec
    errors = validate_target_spec(spec)
    if errors:
        print(f"\n  VALIDATION ERRORS:")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"\n  Validation: PASSED")

    # Generate Dockerfile
    from ndai.enclave.vuln_verify.builder import EIFBuilder
    builder = EIFBuilder()
    dockerfile = builder.generate_dockerfile(spec)
    print(f"\n--- Generated Dockerfile ---")
    print(dockerfile)
