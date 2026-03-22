"""Unit tests for E2E encrypted messaging schemas and deterministic IDs."""

import hashlib
import uuid

from ndai.api.schemas.messaging import (
    PrekeyBundleUpload,
    OTPKUpload,
    ConversationCreate,
    MessageSend,
)


def test_prekey_bundle_upload_schema():
    """Prekey bundle upload should accept valid data."""
    bundle = PrekeyBundleUpload(
        identity_x25519_pub="a" * 64,
        signed_prekey_pub="b" * 64,
        signed_prekey_sig="c" * 128,
        signed_prekey_id=0,
        one_time_prekeys=[
            OTPKUpload(pub="d" * 64, index=0),
            OTPKUpload(pub="e" * 64, index=1),
        ],
    )
    assert bundle.signed_prekey_id == 0
    assert len(bundle.one_time_prekeys) == 2


def test_conversation_create_dm():
    """DM conversation requires peer_pubkey."""
    conv = ConversationCreate(peer_pubkey="abcd1234" * 8)
    assert conv.peer_pubkey is not None
    assert conv.agreement_id is None


def test_conversation_create_deal():
    """Deal conversation requires agreement_id."""
    conv = ConversationCreate(agreement_id="some-uuid")
    assert conv.agreement_id == "some-uuid"
    assert conv.peer_pubkey is None


def test_message_send_schema():
    """Message send requires ciphertext and header."""
    msg = MessageSend(
        ciphertext="base64ciphertext",
        header="base64header",
        x3dh_header="base64x3dh",
    )
    assert msg.x3dh_header == "base64x3dh"


def test_message_send_without_x3dh():
    """Subsequent messages don't need x3dh_header."""
    msg = MessageSend(ciphertext="ct", header="hdr")
    assert msg.x3dh_header is None


def test_deterministic_conversation_id():
    """DM conversation IDs should be deterministic from sorted pubkeys."""
    a = "alice_pub_" + "a" * 54
    b = "bob_pubke" + "b" * 55

    def conv_id(x: str, y: str) -> uuid.UUID:
        sorted_keys = "".join(sorted([x, y]))
        h = hashlib.sha256(sorted_keys.encode()).hexdigest()
        return uuid.UUID(h[:32])

    # Order shouldn't matter
    assert conv_id(a, b) == conv_id(b, a)
    # Different keys → different IDs
    assert conv_id(a, b) != conv_id(a, a)
