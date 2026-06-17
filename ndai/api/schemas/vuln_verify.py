"""Vulnerability verification request/response schemas."""

from pydantic import BaseModel

from ndai.api.schemas.known_target import CAPABILITY_LEVELS


class PackageSpec(BaseModel):
    name: str
    version: str


class ConfigFileSpec(BaseModel):
    path: str
    content: str
    mode: int = 0o644


class ServiceSpecSchema(BaseModel):
    name: str
    start_command: str
    health_check: str
    timeout_sec: int = 30


class PoCSpecSchema(BaseModel):
    script_type: str  # "bash" or "python3"
    script_content: str
    timeout_sec: int = 60


class ClaimedCapabilitySchema(BaseModel):
    # Constrained to the CapabilityLevel enum values so an invalid level is rejected at
    # the API boundary (422) instead of failing later inside the enclave build/verify task.
    level: CAPABILITY_LEVELS
    crash_signal: int | None = None  # Only for level=crash
    exit_code: int | None = None     # Only for level=crash
    reliability_runs: int = 3


class TargetSpecCreateRequest(BaseModel):
    vulnerability_id: str
    base_image: str
    packages: list[PackageSpec]
    config_files: list[ConfigFileSpec] = []
    services: list[ServiceSpecSchema] = []
    poc: PoCSpecSchema
    claimed_capability: ClaimedCapabilitySchema
    service_user: str = "www-data"


class TargetSpecResponse(BaseModel):
    id: str
    vulnerability_id: str
    base_image: str
    package_count: int
    status: str


class EIFManifestResponse(BaseModel):
    spec_id: str
    pcr0: str
    pcr1: str
    pcr2: str
    status: str
    built_at: str | None


class OverlayUploadRequest(BaseModel):
    encrypted_overlay: str  # base64-encoded ECIES ciphertext


class VerificationResultResponse(BaseModel):
    # Boolean verdicts emitted by the verification orchestrator (VerificationOutcome):
    # the rich CapabilityResult is reduced to pass/fail inside the enclave before it
    # crosses the trust boundary (result stripping).
    unpatched_matches: bool
    patched_matches: bool | None = None
    overlap_detected: bool | None = None
    verification_chain_hash: str
    pcr0: str | None = None
