"""Shamir's Secret Sharing over a prime field.

Implements (k, n)-threshold secret sharing as described in the NDAI paper (Section 3.2).
The secret is split into n shares such that any k shares can reconstruct it,
but fewer than k shares reveal nothing about the secret.

Uses a 256-bit prime field to match AES-256 key sizes.
"""

import secrets
from dataclasses import dataclass

# A 256-bit prime (2^256 - 189 is prime)
PRIME = (1 << 256) - 189


@dataclass(frozen=True)
class Share:
    """A single share of a Shamir secret."""

    index: int  # x-coordinate (1-indexed, never 0)
    value: int  # y-coordinate (f(index) mod PRIME)


def _mod_inverse(a: int, p: int) -> int:
    """Compute modular multiplicative inverse using Fermat's little theorem."""
    return pow(a, p - 2, p)


def _eval_polynomial(coefficients: list[int], x: int, prime: int) -> int:
    """Evaluate a polynomial at point x using Horner's method."""
    result = 0
    for coeff in reversed(coefficients):
        result = (result * x + coeff) % prime
    return result


def split(secret: bytes | int, k: int, n: int, prime: int = PRIME) -> list[Share]:
    """Split a secret into n shares with threshold k.

    Args:
        secret: The secret to split (bytes or int). Bytes are interpreted as big-endian.
        k: Minimum shares needed to reconstruct (threshold).
        n: Total number of shares to generate.
        prime: The prime field modulus.

    Returns:
        List of n Share objects.

    Raises:
        ValueError: If parameters are invalid.
    """
    if k < 2:
        raise ValueError("Threshold k must be >= 2")
    if n < k:
        raise ValueError(f"Total shares n={n} must be >= threshold k={k}")
    if k > 255:
        raise ValueError("Threshold k must be <= 255")

    if isinstance(secret, bytes):
        secret_int = int.from_bytes(secret, "big")
    else:
        secret_int = secret

    if secret_int < 0 or secret_int >= prime:
        raise ValueError(f"Secret must be in range [0, {prime})")

    # Generate random polynomial coefficients: f(x) = secret + a1*x + a2*x^2 + ... + a_{k-1}*x^{k-1}
    coefficients = [secret_int] + [secrets.randbelow(prime) for _ in range(k - 1)]

    shares = []
    for i in range(1, n + 1):
        y = _eval_polynomial(coefficients, i, prime)
        shares.append(Share(index=i, value=y))

    return shares


def reconstruct(shares: list[Share], prime: int = PRIME) -> int:
    """Reconstruct the secret from k or more shares using Lagrange interpolation.

    Args:
        shares: List of shares (must have at least k shares).
        prime: The prime field modulus.

    Returns:
        The reconstructed secret as an integer.

    Raises:
        ValueError: If fewer than 2 shares provided or duplicate indices found.
    """
    if len(shares) < 2:
        raise ValueError("Need at least 2 shares to reconstruct")

    indices = [s.index for s in shares]
    if len(set(indices)) != len(indices):
        raise ValueError("Duplicate share indices")

    # Lagrange interpolation at x=0
    secret = 0
    for i, share_i in enumerate(shares):
        numerator = 1
        denominator = 1
        for j, share_j in enumerate(shares):
            if i == j:
                continue
            numerator = (numerator * (-share_j.index)) % prime
            denominator = (denominator * (share_i.index - share_j.index)) % prime

        lagrange = (share_i.value * numerator * _mod_inverse(denominator, prime)) % prime
        secret = (secret + lagrange) % prime

    return secret


def reconstruct_bytes(shares: list[Share], length: int = 32, prime: int = PRIME) -> bytes:
    """Reconstruct the secret and return as bytes.

    Args:
        shares: List of shares.
        length: Expected byte length of the secret.
        prime: The prime field modulus.

    Returns:
        The reconstructed secret as bytes (big-endian).
    """
    secret_int = reconstruct(shares, prime)
    return secret_int.to_bytes(length, "big")
