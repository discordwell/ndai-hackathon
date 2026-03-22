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


class ExpectedOutcomeSchema(BaseModel):
    exit_code: int | None = None
    stdout_contains: str | None = None
    stderr_contains: str | None = None
    crash_signal: int | None = None


class TargetSpecCreateRequest(BaseModel):
    vulnerability_id: str
    base_image: str
    packages: list[PackageSpec]
    config_files: list[ConfigFileSpec] = []
    services: list[ServiceSpecSchema] = []
    poc: PoCSpecSchema
    expected_outcome: ExpectedOutcomeSchema


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
    unpatched_matches: bool
    patched_matches: bool | None = None
    overlap_detected: bool | None = None
    verification_chain_hash: str
    pcr0: str | None = None
