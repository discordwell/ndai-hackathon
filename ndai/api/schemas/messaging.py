"""E2E encrypted messaging request/response schemas."""

from pydantic import BaseModel, Field


# --- Prekey upload ---


class OTPKUpload(BaseModel):
    pub: str = Field(max_length=64)
    index: int


class PrekeyBundleUpload(BaseModel):
    identity_x25519_pub: str = Field(max_length=64)
    signed_prekey_pub: str = Field(max_length=64)
    signed_prekey_sig: str = Field(max_length=128)
    signed_prekey_id: int
    one_time_prekeys: list[OTPKUpload]


# --- Prekey fetch response ---


class OTPKResponse(BaseModel):
    pub: str
    index: int


class PrekeyBundleResponse(BaseModel):
    identity_pubkey: str  # Ed25519
    identity_x25519_pub: str
    signed_prekey_pub: str
    signed_prekey_sig: str
    signed_prekey_id: int
    one_time_prekey: OTPKResponse | None  # may be exhausted


class PrekeyStatusResponse(BaseModel):
    remaining_otpks: int
    signed_prekey_age_hours: float


# --- Conversations ---


class ConversationCreate(BaseModel):
    peer_pubkey: str | None = None  # for DM
    agreement_id: str | None = None  # for deal chat


class ConversationResponse(BaseModel):
    id: str
    type: str
    agreement_id: str | None
    participant_a: str
    participant_b: str
    created_at: str
    last_message_at: str | None = None
    unread_count: int = 0


# --- Messages ---


class MessageSend(BaseModel):
    ciphertext: str  # base64
    header: str  # base64
    x3dh_header: str | None = None  # base64, first message only


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_pubkey: str
    ciphertext: str
    header: str
    x3dh_header: str | None
    message_index: int
    created_at: str
