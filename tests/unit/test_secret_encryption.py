"""Tests for AES-256-GCM secret encryption."""

import os

import pytest

from ndai.crypto.secret_encryption import decrypt_secret, encrypt_secret


def _random_key_hex():
    return os.urandom(32).hex()


def test_encrypt_decrypt_roundtrip():
    key = _random_key_hex()
    plaintext = "AKIAIOSFODNN7EXAMPLE"
    ciphertext = encrypt_secret(plaintext, key)
    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext, key) == plaintext


def test_different_keys_fail():
    key1 = _random_key_hex()
    key2 = _random_key_hex()
    ciphertext = encrypt_secret("secret", key1)
    with pytest.raises(Exception):
        decrypt_secret(ciphertext, key2)


def test_ciphertext_is_hex():
    key = _random_key_hex()
    ciphertext = encrypt_secret("test", key)
    # Should be valid hex
    bytes.fromhex(ciphertext)


def test_invalid_key_length():
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt_secret("test", "aabbcc")


def test_each_encryption_is_unique():
    key = _random_key_hex()
    c1 = encrypt_secret("same", key)
    c2 = encrypt_secret("same", key)
    assert c1 != c2  # Different nonces
    assert decrypt_secret(c1, key) == decrypt_secret(c2, key) == "same"
