"""Data models for PoC verification in the zero-day marketplace.

All models are frozen dataclasses — immutable after construction.
TargetSpec and BuyerOverlay cross the trust boundary: TargetSpec comes from
the seller (untrusted), BuyerOverlay comes from the buyer (encrypted to enclave).
Both must be validated before use.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


# ---------------------------------------------------------------------------
# Seller-provided target specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PinnedPackage:
    """An apt package with an exact version pin."""
    name: str       # e.g., "apache2"
    version: str    # e.g., "2.4.52-1ubuntu4.3"


@dataclass(frozen=True)
class ConfigFile:
    """A configuration file to place in the target environment."""
    path: str       # absolute path, e.g., "/etc/apache2/sites-enabled/000-default.conf"
    content: str    # text content
    mode: int = 0o644


@dataclass(frozen=True)
class ServiceSpec:
    """A service to start in the target environment before PoC execution."""
    name: str           # e.g., "apache2"
    start_command: str  # e.g., "service apache2 start"
    health_check: str   # e.g., "curl -sf http://localhost/ > /dev/null"
    timeout_sec: int = 30


@dataclass(frozen=True)
class PoCSpec:
    """The proof-of-concept script that exercises the vulnerability."""
    script_type: str    # "bash" or "python3"
    script_content: str # the PoC script body
    timeout_sec: int = 60
    run_as_user: str = "poc"  # non-root user for PoC execution


class CapabilityLevel(Enum):
    """What a 0day exploit can achieve, ordered by value."""
    CRASH = "crash"           # Target process terminates (lowest value)
    DOS = "dos"               # Target becomes unresponsive
    INFO_LEAK = "info_leak"   # Exploit reads inaccessible data
    ACE = "ace"               # Arbitrary code execution as service user
    LPE = "lpe"               # Local privilege escalation (service → root)
    CALLBACK = "callback"     # Blind RCE (triggers outbound connection)


@dataclass(frozen=True)
class ClaimedCapability:
    """What the seller claims their exploit can do.

    The enclave independently verifies this claim using oracles.
    The seller does NOT define what success looks like — they only
    declare the capability level. The enclave generates the challenge.
    """
    level: CapabilityLevel
    # Legacy crash fields (only used when level=CRASH)
    crash_signal: int | None = None
    exit_code: int | None = None
    # Reliability: how many times to run the PoC
    reliability_runs: int = 3


@dataclass(frozen=True)
class CapabilityResult:
    """Enclave-verified capability assessment.

    This is what the buyer sees. It answers: "What can this exploit
    actually do?" not just "did it crash?"
    """
    claimed: CapabilityLevel
    verified_level: CapabilityLevel | None  # Highest level confirmed, or None
    ace_canary_found: bool = False
    lpe_canary_found: bool = False
    info_canary_found: bool = False
    callback_received: bool = False
    crash_detected: bool = False
    dos_detected: bool = False
    reliability_score: float = 0.0   # successes / attempts
    reliability_runs: int = 1


# Keep ExpectedOutcome for backward compatibility but mark as legacy
@dataclass(frozen=True)
class ExpectedOutcome:
    """Legacy: What a successful PoC execution looks like. Use ClaimedCapability instead."""
    exit_code: int | None = None
    stdout_contains: str | None = None
    stderr_contains: str | None = None
    crash_signal: int | None = None


@dataclass(frozen=True)
class TargetSpec:
    """Seller-provided specification of the vulnerable software environment.

    This defines everything needed to build a per-target EIF:
    - Base OS image (must be whitelisted)
    - Packages with pinned versions
    - Configuration files
    - Services to start
    - The PoC script and expected outcome
    """
    spec_id: str
    base_image: str                   # e.g., "ubuntu:22.04"
    packages: list[PinnedPackage]
    config_files: list[ConfigFile]
    services: list[ServiceSpec]
    poc: PoCSpec
    claimed_capability: ClaimedCapability
    # Service user that the target runs as (for oracle permission setup)
    service_user: str = "www-data"
    # Legacy field, kept for backward compat
    expected_outcome: ExpectedOutcome = field(default_factory=ExpectedOutcome)


# ---------------------------------------------------------------------------
# Buyer-provided overlay (encrypted, never visible to seller)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileReplacement:
    """A single file to replace in the target environment."""
    path: str       # absolute path of file to replace
    content: bytes  # raw binary content


@dataclass(frozen=True)
class BuyerOverlay:
    """Buyer-provided patched file replacements, encrypted to enclave.

    The buyer (e.g., an intelligence agency) provides binary replacements
    for files in the target environment. These represent the buyer's own
    patches for vulnerabilities they already own. If the seller's PoC
    still works after applying the overlay, the 0day is genuinely new.

    The overlay is ECIES-encrypted to the enclave's ephemeral public key.
    The seller never sees any of this.
    """
    overlay_id: str
    file_replacements: list[FileReplacement]
    pre_apply_commands: list[str] = field(default_factory=list)   # e.g., ["service apache2 stop"]
    post_apply_commands: list[str] = field(default_factory=list)  # e.g., ["service apache2 start"]


# ---------------------------------------------------------------------------
# Execution results
# ---------------------------------------------------------------------------

MAX_OUTPUT_BYTES = 65536  # 64KB cap on captured stdout/stderr


@dataclass(frozen=True)
class PoCResult:
    """Captured result of a single PoC execution."""
    exit_code: int
    stdout: str          # truncated to MAX_OUTPUT_BYTES
    stderr: str          # truncated to MAX_OUTPUT_BYTES
    signal: int | None   # if killed by signal (e.g., 11 = SIGSEGV)
    timed_out: bool
    duration_sec: float


@dataclass(frozen=True)
class VerificationResult:
    """Attestation-signed verification output.

    This is what leaves the enclave. stdout/stderr do NOT leave —
    only capability assessments and the chain hash.

    The buyer sees: "ACE verified, reliability 9/10, LPE not achieved"
    instead of just "crash confirmed."
    """
    spec_id: str
    unpatched_capability: CapabilityResult    # What was verified on unpatched target
    patched_capability: CapabilityResult | None  # What was verified on patched target
    overlap_detected: bool | None             # True if exploit survives buyer's patches
    verification_chain_hash: str              # SHA-256 final hash from event chain
    timestamp: str                            # ISO 8601


@dataclass(frozen=True)
class EIFManifest:
    """Build artifact metadata for a per-target EIF."""
    spec_id: str
    eif_path: str
    pcr0: str              # SHA-384 of EIF image
    pcr1: str              # SHA-384 of kernel
    pcr2: str              # SHA-384 of application
    base_image: str
    package_count: int
    docker_image_hash: str
    built_at: str          # ISO 8601


# ---------------------------------------------------------------------------
# Resource limits for PoC execution
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResourceLimits:
    """Resource constraints for PoC script execution."""
    max_cpu_sec: int = 60          # CPU time limit (RLIMIT_CPU)
    max_memory_mb: int = 512       # RSS limit (RLIMIT_AS)
    max_output_bytes: int = MAX_OUTPUT_BYTES  # stdout/stderr cap
    max_wall_sec: int = 120        # wall clock timeout
    max_processes: int = 64        # fork limit (RLIMIT_NPROC)
    max_file_size_mb: int = 100    # output file size limit (RLIMIT_FSIZE)
