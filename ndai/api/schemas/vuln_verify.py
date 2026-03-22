"""Vulnerability verification request/response schemas."""

from pydantic import BaseModel, Field


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
    level: str  # "crash" | "dos" | "info_leak" | "ace" | "lpe" | "callback"
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


class CapabilityResultSchema(BaseModel):
    claimed: str                          # Capability level claimed
    verified_level: str | None = None     # Highest level confirmed
    ace_canary_found: bool = False
    lpe_canary_found: bool = False
    info_canary_found: bool = False
    callback_received: bool = False
    crash_detected: bool = False
    dos_detected: bool = False
    reliability_score: float = 0.0
    reliability_runs: int = 1


class VerificationResultResponse(BaseModel):
    unpatched_capability: CapabilityResultSchema
    patched_capability: CapabilityResultSchema | None = None
    overlap_detected: bool | None = None
    verification_chain_hash: str
    pcr0: str | None = None
