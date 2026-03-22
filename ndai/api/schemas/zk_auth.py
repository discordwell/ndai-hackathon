"""ZK authentication request/response schemas."""

from pydantic import BaseModel, Field


class ZKRegisterRequest(BaseModel):
    public_key: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    signature: str = Field(..., pattern=r"^[0-9a-fA-F]+$")
    alias: str | None = None


class ZKRegisterResponse(BaseModel):
    status: str


class ZKChallengeRequest(BaseModel):
    public_key: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")


class ZKChallengeResponse(BaseModel):
    nonce: str


class ZKVerifyRequest(BaseModel):
    public_key: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    nonce: str = Field(..., pattern=r"^[0-9a-fA-F]+$")
    signature: str = Field(..., pattern=r"^[0-9a-fA-F]+$")


class ZKVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
