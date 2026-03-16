"""Shared test fixtures."""

import os

import pytest

# Ensure test database URL is set before any imports of ndai.config
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://ndai:ndai@localhost:5433/ndai",
)


@pytest.fixture
def sample_invention():
    """A sample invention for testing negotiation flows."""
    return {
        "title": "Quantum-Resistant Lattice Key Exchange",
        "full_description": (
            "A novel key exchange protocol based on structured lattices that achieves "
            "post-quantum security with O(n log n) computation complexity. The protocol "
            "uses a new ring-LWE variant with tighter security reductions."
        ),
        "technical_domain": "cryptography",
        "novelty_claims": [
            "New ring-LWE variant with 30% tighter security reduction",
            "Efficient implementation using NTT-friendly primes",
            "Formal verification of protocol correctness in Lean4",
        ],
        "prior_art_known": ["CRYSTALS-Kyber", "NewHope", "FrodoKEM"],
        "potential_applications": [
            "TLS 1.4 post-quantum handshake",
            "Secure messaging protocols",
            "IoT device authentication",
        ],
        "development_stage": "prototype",
        "self_assessed_value": 0.75,
        "outside_option_value": 0.3,
        "confidential_sections": ["NTT optimization trick", "Security proof technique"],
        "max_disclosure_fraction": 0.8,
    }
