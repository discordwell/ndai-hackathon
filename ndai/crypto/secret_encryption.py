"""AES-256-GCM encryption for secrets at rest.

Uses the same AESGCM pattern as ndai/enclave/ephemeral_keys.py and
ndai/enclave/vuln_verify/sealed_delivery.py.
"""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_SIZE = 32  # AES-256
_NONCE_SIZE = 12


def _derive_key(key_hex: str) -> bytes:
    """Convert a hex-encoded key string to bytes, validating length."""
    key_bytes = bytes.fromhex(key_hex)
    if len(key_bytes) != _KEY_SIZE:
        raise ValueError(f"Encryption key must be {_KEY_SIZE} bytes ({_KEY_SIZE * 2} hex chars)")
    return key_bytes


def encrypt_secret(plaintext: str, key_hex: str) -> str:
    """Encrypt a secret value with AES-256-GCM.

    Returns hex-encoded nonce + ciphertext.
    """
    key = _derive_key(key_hex)
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return (nonce + ciphertext).hex()


def decrypt_secret(ciphertext_hex: str, key_hex: str) -> str:
    """Decrypt a secret value encrypted with encrypt_secret().

    Returns the plaintext string.
    """
    key = _derive_key(key_hex)
    raw = bytes.fromhex(ciphertext_hex)
    nonce = raw[:_NONCE_SIZE]
    ciphertext = raw[_NONCE_SIZE:]
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
