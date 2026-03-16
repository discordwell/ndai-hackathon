"""Tests for ECDSA sign/verify in ephemeral_keys."""

import pytest

from ndai.enclave.ephemeral_keys import generate_keypair, sign_data, verify_signature


class TestSignVerify:
    def test_sign_and_verify(self):
        kp = generate_keypair()
        data = b"test transcript hash"
        sig = sign_data(kp.private_key, data)
        assert verify_signature(kp.public_key, sig, data) is True

    def test_verify_fails_with_wrong_data(self):
        kp = generate_keypair()
        sig = sign_data(kp.private_key, b"original")
        assert verify_signature(kp.public_key, sig, b"tampered") is False

    def test_verify_fails_with_wrong_key(self):
        kp1 = generate_keypair()
        kp2 = generate_keypair()
        sig = sign_data(kp1.private_key, b"data")
        assert verify_signature(kp2.public_key, sig, b"data") is False

    def test_sign_returns_bytes(self):
        kp = generate_keypair()
        sig = sign_data(kp.private_key, b"hello")
        assert isinstance(sig, bytes)
        assert len(sig) > 0
