"""Unit tests for EscrowClient — no Anvil required."""

from unittest.mock import patch

import pytest

# Mock _load_abi before importing EscrowClient so the constructor
# doesn't try to open Forge artifacts (not available in CI).
_FAKE_ABI: list[dict] = [{"type": "function", "name": "stub", "inputs": [], "outputs": []}]

with patch("ndai.blockchain.escrow_client._load_abi", return_value=_FAKE_ABI):
    from ndai.blockchain.escrow_client import EscrowClient

VALID_FACTORY = "0x1234567890123456789012345678901234567890"
VALID_RPC = "http://localhost:8545"


class TestEscrowClientConstructor:
    def test_valid_address_succeeds(self) -> None:
        client = EscrowClient(VALID_RPC, VALID_FACTORY)
        assert client._factory_address == VALID_FACTORY

    def test_invalid_address_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid factory address"):
            EscrowClient(VALID_RPC, "not-an-address")

    def test_empty_address_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid factory address"):
            EscrowClient(VALID_RPC, "")

    def test_short_hex_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid factory address"):
            EscrowClient(VALID_RPC, "0xdeadbeef")

    def test_default_chain_id(self) -> None:
        client = EscrowClient(VALID_RPC, VALID_FACTORY)
        assert client._chain_id == 84532

    def test_custom_chain_id(self) -> None:
        client = EscrowClient(VALID_RPC, VALID_FACTORY, chain_id=1)
        assert client._chain_id == 1

    def test_checksums_address(self) -> None:
        # Use an address with letters so EIP-55 checksum changes the casing.
        # This address has alphabetic hex digits that will be upper-cased by EIP-55.
        addr_with_letters = "0xabcdef1234567890abcdef1234567890abcdef12"
        client = EscrowClient(VALID_RPC, addr_with_letters)
        # Stored address should be valid and round-trip through lower().
        assert client._factory_address.lower() == addr_with_letters
        # The stored address must be accepted by web3 as a checksum address.
        from web3 import AsyncWeb3
        assert AsyncWeb3.is_address(client._factory_address)


class TestCreateDealSignature:
    def test_create_deal_does_not_accept_buyer_address(self):
        import inspect
        from ndai.blockchain.escrow_client import EscrowClient
        sig = inspect.signature(EscrowClient.create_deal)
        param_names = list(sig.parameters.keys())
        assert "buyer_address" not in param_names
        assert "seller_address" in param_names
        assert "operator_address" in param_names


class TestComputeAttestationHash:
    PCR0 = b"\x00" * 48
    NONCE = b"test-nonce"
    OUTCOME = b'{"price": 1000}'

    def test_returns_32_bytes(self) -> None:
        digest = EscrowClient.compute_attestation_hash(self.PCR0, self.NONCE, self.OUTCOME)
        assert isinstance(digest, bytes)
        assert len(digest) == 32

    def test_deterministic(self) -> None:
        a = EscrowClient.compute_attestation_hash(self.PCR0, self.NONCE, self.OUTCOME)
        b = EscrowClient.compute_attestation_hash(self.PCR0, self.NONCE, self.OUTCOME)
        assert a == b

    def test_different_pcr0_gives_different_hash(self) -> None:
        a = EscrowClient.compute_attestation_hash(self.PCR0, self.NONCE, self.OUTCOME)
        b = EscrowClient.compute_attestation_hash(b"\xff" * 48, self.NONCE, self.OUTCOME)
        assert a != b

    def test_different_nonce_gives_different_hash(self) -> None:
        a = EscrowClient.compute_attestation_hash(self.PCR0, self.NONCE, self.OUTCOME)
        b = EscrowClient.compute_attestation_hash(self.PCR0, b"other-nonce", self.OUTCOME)
        assert a != b

    def test_different_outcome_gives_different_hash(self) -> None:
        a = EscrowClient.compute_attestation_hash(self.PCR0, self.NONCE, self.OUTCOME)
        b = EscrowClient.compute_attestation_hash(self.PCR0, self.NONCE, b'{"price": 9999}')
        assert a != b

    def test_empty_inputs_still_returns_32_bytes(self) -> None:
        digest = EscrowClient.compute_attestation_hash(b"", b"", b"")
        assert len(digest) == 32
