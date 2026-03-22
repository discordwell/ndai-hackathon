"""Security validation for PoC verification inputs.

All seller-provided inputs (TargetSpec) and buyer-provided inputs (BuyerOverlay)
must pass validation before use. This module enforces:
- Base image whitelist
- Package name/version format validation
- Config file path restrictions
- PoC script sanitization
- Overlay path restrictions and size limits
"""

import re

from ndai.enclave.vuln_verify.models import (
    BuyerOverlay,
    ConfigFile,
    PinnedPackage,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)

# ---------------------------------------------------------------------------
# Whitelists and patterns
# ---------------------------------------------------------------------------

ALLOWED_BASE_IMAGES = frozenset({
    "ubuntu:20.04",
    "ubuntu:22.04",
    "ubuntu:24.04",
    "debian:11",
    "debian:12",
    "amazonlinux:2",
    "amazonlinux:2023",
})

# apt package name: lowercase alphanumeric, dots, plus, hyphens
PACKAGE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.+\-]+$")

# apt package version: alphanumeric, dots, plus, hyphens, colons, tildes
PACKAGE_VERSION_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.+\-:~]+$")

# Config files restricted to /etc/ subtree
CONFIG_PATH_PATTERN = re.compile(r"^/etc/[a-zA-Z0-9/_.\-]+$")

# Overlay replacement paths — restricted to safe directories
OVERLAY_ALLOWED_PREFIXES = (
    "/usr/lib/",
    "/usr/bin/",
    "/usr/sbin/",
    "/opt/",
    "/lib/",
    "/lib64/",
)

# Known safe service start/stop patterns
SERVICE_COMMAND_PATTERN = re.compile(
    r"^(service\s+[a-z0-9\-]+\s+(start|stop|restart|reload)"
    r"|systemctl\s+(start|stop|restart|reload)\s+[a-z0-9\-]+\.service"
    r"|/etc/init\.d/[a-z0-9\-]+\s+(start|stop|restart))$"
)

# Health check patterns (curl, wget, or simple test commands)
HEALTH_CHECK_PATTERN = re.compile(
    r"^(curl\s+-[sf]+\s+http://localhost[:/].*"
    r"|wget\s+-q\s+-O\s*/dev/null\s+http://localhost[:/].*"
    r"|test\s+-[feSp]\s+/[a-zA-Z0-9/_.\-]+"
    r"|true)$"
)

# Dangerous patterns in PoC scripts
POC_DANGEROUS_PATTERNS = [
    re.compile(r"rm\s+-rf\s+/", re.IGNORECASE),
    re.compile(r"mkfs\.", re.IGNORECASE),
    re.compile(r"dd\s+if=.+of=/dev/", re.IGNORECASE),
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r"/app/ndai/", re.IGNORECASE),     # Don't touch the enclave runtime
    re.compile(r"ephemeral_key", re.IGNORECASE),   # Don't access enclave keys
    re.compile(r"api_key", re.IGNORECASE),          # Don't access delivered keys
    re.compile(r"curl\s+.*\|.*sh", re.IGNORECASE),  # No pipe to shell
    re.compile(r"wget\s+.*\|.*sh", re.IGNORECASE),
    re.compile(r"pip\s+install", re.IGNORECASE),    # No package installation in PoC
]

# Size limits
MAX_CONFIG_FILE_SIZE = 1 * 1024 * 1024     # 1 MB per config file
MAX_CONFIG_FILE_COUNT = 20
MAX_POC_SCRIPT_SIZE = 256 * 1024           # 256 KB
MAX_PACKAGE_COUNT = 50
MAX_SERVICE_COUNT = 10
MAX_OVERLAY_FILE_SIZE = 100 * 1024 * 1024  # 100 MB per replacement file
MAX_OVERLAY_TOTAL_SIZE = 500 * 1024 * 1024 # 500 MB total overlay
MAX_OVERLAY_FILE_COUNT = 50


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_target_spec(spec: TargetSpec) -> list[str]:
    """Validate a seller-provided target specification.

    Returns list of validation errors. Empty list means valid.
    """
    errors: list[str] = []

    # Base image whitelist
    if spec.base_image not in ALLOWED_BASE_IMAGES:
        errors.append(
            f"Base image '{spec.base_image}' not in allowed list: "
            f"{sorted(ALLOWED_BASE_IMAGES)}"
        )

    # Package validation
    if len(spec.packages) > MAX_PACKAGE_COUNT:
        errors.append(f"Too many packages: {len(spec.packages)} > {MAX_PACKAGE_COUNT}")

    for pkg in spec.packages:
        if not PACKAGE_NAME_PATTERN.match(pkg.name):
            errors.append(f"Invalid package name: '{pkg.name}'")
        if not PACKAGE_VERSION_PATTERN.match(pkg.version):
            errors.append(f"Invalid package version for {pkg.name}: '{pkg.version}'")

    # Config file validation
    if len(spec.config_files) > MAX_CONFIG_FILE_COUNT:
        errors.append(f"Too many config files: {len(spec.config_files)} > {MAX_CONFIG_FILE_COUNT}")

    for cf in spec.config_files:
        if not CONFIG_PATH_PATTERN.match(cf.path):
            errors.append(f"Config path not allowed: '{cf.path}' (must be under /etc/)")
        if ".." in cf.path:
            errors.append(f"Path traversal in config path: '{cf.path}'")
        if len(cf.content.encode("utf-8")) > MAX_CONFIG_FILE_SIZE:
            errors.append(f"Config file too large: '{cf.path}' > {MAX_CONFIG_FILE_SIZE} bytes")

    # Service validation
    if len(spec.services) > MAX_SERVICE_COUNT:
        errors.append(f"Too many services: {len(spec.services)} > {MAX_SERVICE_COUNT}")

    for svc in spec.services:
        if not SERVICE_COMMAND_PATTERN.match(svc.start_command):
            errors.append(f"Invalid service command: '{svc.start_command}'")
        if not HEALTH_CHECK_PATTERN.match(svc.health_check):
            errors.append(f"Invalid health check: '{svc.health_check}'")

    # PoC validation
    errors.extend(_validate_poc(spec.poc))

    return errors


def _validate_poc(poc: PoCSpec) -> list[str]:
    """Validate the PoC script."""
    errors: list[str] = []

    if poc.script_type not in ("bash", "python3"):
        errors.append(f"Invalid PoC script type: '{poc.script_type}' (must be 'bash' or 'python3')")

    if len(poc.script_content.encode("utf-8")) > MAX_POC_SCRIPT_SIZE:
        errors.append(f"PoC script too large: > {MAX_POC_SCRIPT_SIZE} bytes")

    if poc.timeout_sec <= 0 or poc.timeout_sec > 300:
        errors.append(f"PoC timeout must be 1-300 seconds, got {poc.timeout_sec}")

    # Check for dangerous patterns
    for pattern in POC_DANGEROUS_PATTERNS:
        if pattern.search(poc.script_content):
            errors.append(f"Dangerous pattern in PoC script: {pattern.pattern}")

    return errors


def validate_buyer_overlay(overlay: BuyerOverlay) -> list[str]:
    """Validate a buyer-provided overlay.

    Returns list of validation errors. Empty list means valid.
    """
    errors: list[str] = []

    if len(overlay.file_replacements) > MAX_OVERLAY_FILE_COUNT:
        errors.append(
            f"Too many overlay files: {len(overlay.file_replacements)} > {MAX_OVERLAY_FILE_COUNT}"
        )

    total_size = 0
    for fr in overlay.file_replacements:
        # Path restrictions
        if not any(fr.path.startswith(prefix) for prefix in OVERLAY_ALLOWED_PREFIXES):
            errors.append(
                f"Overlay path not allowed: '{fr.path}' "
                f"(must start with one of {OVERLAY_ALLOWED_PREFIXES})"
            )
        if ".." in fr.path:
            errors.append(f"Path traversal in overlay path: '{fr.path}'")

        # Size limits
        size = len(fr.content)
        if size > MAX_OVERLAY_FILE_SIZE:
            errors.append(f"Overlay file too large: '{fr.path}' ({size} > {MAX_OVERLAY_FILE_SIZE})")
        total_size += size

    if total_size > MAX_OVERLAY_TOTAL_SIZE:
        errors.append(f"Total overlay size too large: {total_size} > {MAX_OVERLAY_TOTAL_SIZE}")

    # Validate pre/post commands
    all_commands = list(overlay.pre_apply_commands) + list(overlay.post_apply_commands)
    for cmd in all_commands:
        if not SERVICE_COMMAND_PATTERN.match(cmd):
            errors.append(f"Invalid overlay command: '{cmd}'")

    return errors


def sanitize_poc_script(script: str, script_type: str) -> str:
    """Remove or neutralize dangerous patterns from a PoC script.

    This is a defense-in-depth measure — validation should catch
    dangerous scripts, but sanitization provides an extra layer.
    """
    sanitized = script

    # Remove attempts to access enclave internals
    sanitized = re.sub(r"/app/ndai/[^\s]*", "/dev/null", sanitized)

    # Remove attempts to write to /dev/ block devices
    sanitized = re.sub(r">/dev/sd[a-z]\d*", ">/dev/null", sanitized)

    return sanitized
