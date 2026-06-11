"""Tests for the parent-side PoC verification orchestrator.

Focus: the Nitro key-delivery path (`_run_nitro`), which is never exercised
by CI (no Nitro hardware) and previously read a non-existent attestation
attribute, guaranteeing an AttributeError the moment an API key was delivered.
"""

import pytest

from ndai.enclave.ephemeral_keys import decrypt_api_key, generate_keypair
from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    ClaimedCapability,
    ConfigFile,
    PinnedPackage,
    PoCSpec,
    ServiceSpec,
    TargetSpec,
)
from ndai.tee import vuln_verify_orchestrator as vvo
from ndai.tee.attestation import AttestationResult
from ndai.tee.provider import EnclaveConfig, EnclaveIdentity, TEEProvider, TEEType


def _make_spec() -> TargetSpec:
    return TargetSpec(
        spec_id="test-spec-1",
        base_image="ubuntu:22.04",
        packages=[PinnedPackage("apache2", "2.4.52-1ubuntu4.3")],
        config_files=[ConfigFile("/etc/apache2/ports.conf", "Listen 80")],
        services=[ServiceSpec("apache2", "service apache2 start", "curl -sf http://localhost/ > /dev/null")],
        poc=PoCSpec("bash", "curl -s http://localhost/ -H 'X-Evil: test'"),
        claimed_capability=ClaimedCapability(level=CapabilityLevel.ACE),
    )


class FakeNitroProvider(TEEProvider):
    """Minimal in-memory provider that scripts the enclave's vsock replies.

    Records every message the orchestrator sends so tests can inspect what
    was actually delivered (e.g. the ECIES-encrypted API key).
    """

    def __init__(self) -> None:
        self.sent: list[dict] = []
        # Replies are returned in order for each receive_message() call.
        self._replies = [
            {"status": "ok"},  # deliver_key ack
            {
                "status": "ok",
                "result": {
                    "unpatched_capability": {"verified_level": "ace"},
                    "patched_capability": None,
                    "overlap_detected": False,
                    "verification_chain_hash": "deadbeef",
                    "timestamp": "2026-01-01T00:00:00Z",
                },
            },
        ]
        self.terminated: list[str] = []

    def get_tee_type(self) -> TEEType:
        return TEEType.NITRO

    async def launch_enclave(self, config: EnclaveConfig) -> EnclaveIdentity:
        return EnclaveIdentity(
            enclave_id="enc-1",
            enclave_cid=16,
            pcr0="00" * 48,
            pcr1="11" * 48,
            pcr2="22" * 48,
            tee_type=TEEType.NITRO,
        )

    async def get_attestation(self, enclave_id: str, nonce: bytes | None = None) -> bytes:
        return b"fake-attestation-doc"

    async def send_message(self, enclave_id: str, message: dict) -> None:
        self.sent.append(message)

    async def receive_message(self, enclave_id: str) -> dict:
        return self._replies.pop(0)

    async def terminate_enclave(self, enclave_id: str) -> None:
        self.terminated.append(enclave_id)


async def test_nitro_delivers_decryptable_api_key(monkeypatch):
    """The Nitro path must ECIES-encrypt the API key to the enclave's attested
    key such that the enclave can recover it — and must not crash on a
    mistyped attestation attribute."""
    keypair = generate_keypair()

    # verify_attestation is exercised elsewhere; here we pin its output so the
    # orchestrator receives an attestation carrying the enclave's real pubkey.
    def fake_verify(doc, expected_pcrs=None, nonce=None, **kwargs):
        return AttestationResult(
            valid=True,
            pcrs={0: "00" * 48},
            enclave_cid=16,
            timestamp=None,
            enclave_public_key=keypair.public_key_der,
        )

    monkeypatch.setattr(vvo, "verify_attestation", fake_verify)

    provider = FakeNitroProvider()
    orch = vvo.VulnVerifyOrchestrator(provider)
    config = vvo.VerificationConfig(target_spec=_make_spec(), api_key="sk-secret-123")

    outcome = await orch.run_verification(config)

    # The orchestrator completed and tore the enclave down.
    assert outcome.unpatched_matches is True
    assert provider.terminated == ["enc-1"]

    # The first message must be the encrypted key delivery.
    deliver = provider.sent[0]
    assert deliver["action"] == "deliver_key"

    # And the delivered ciphertext must decrypt back to the original key
    # using the enclave's private key — proving correct ECIES, not just
    # "didn't raise".
    encrypted = bytes(deliver["encrypted_key"])
    recovered = decrypt_api_key(keypair.private_key, encrypted)
    assert recovered == "sk-secret-123"


async def test_nitro_fails_closed_without_enclave_pubkey(monkeypatch):
    """If the attestation carries no public key, key delivery must fail closed
    rather than silently proceeding without an encrypted channel."""
    def fake_verify(doc, expected_pcrs=None, nonce=None, **kwargs):
        return AttestationResult(
            valid=True,
            pcrs={0: "00" * 48},
            enclave_cid=16,
            timestamp=None,
            enclave_public_key=None,
        )

    monkeypatch.setattr(vvo, "verify_attestation", fake_verify)

    provider = FakeNitroProvider()
    orch = vvo.VulnVerifyOrchestrator(provider)
    config = vvo.VerificationConfig(target_spec=_make_spec(), api_key="sk-secret-123")

    with pytest.raises(vvo.VerificationOrchestrationError, match="no enclave public key"):
        await orch.run_verification(config)

    # No key delivery should have been attempted.
    assert all(m.get("action") != "deliver_key" for m in provider.sent)
    # Enclave still torn down on the error path.
    assert provider.terminated == ["enc-1"]
