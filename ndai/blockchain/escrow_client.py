"""Async web3.py wrapper for NdaiEscrow and NdaiEscrowFactory contracts."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from ndai.blockchain.models import DealState, EscrowState

logger = logging.getLogger(__name__)

# Absolute path to the compiled Foundry output directory.
_CONTRACTS_OUT = Path(__file__).resolve().parents[2] / "contracts" / "out"


def _load_abi(name: str) -> list[dict[str, Any]]:
    """Load a compiled ABI from contracts/out/{name}/{stem}.json.

    Args:
        name: Solidity source filename, e.g. "NdaiEscrow.sol".

    Returns:
        The ABI as a list of dicts.
    """
    stem = name.split(".")[0]
    artifact_path = _CONTRACTS_OUT / name / f"{stem}.json"
    with artifact_path.open() as f:
        artifact = json.load(f)
    return artifact["abi"]


class EscrowClient:
    """Async client for the NdaiEscrow/NdaiEscrowFactory contracts.

    Args:
        rpc_url: JSON-RPC endpoint URL (e.g. Base Sepolia).
        factory_address: Checksummed address of the deployed NdaiEscrowFactory.
        chain_id: EIP-155 chain ID (default 84532 = Base Sepolia).
    """

    def __init__(self, rpc_url: str, factory_address: str, chain_id: int = 84532) -> None:
        if not AsyncWeb3.is_address(factory_address):
            raise ValueError(f"Invalid factory address: {factory_address!r}")

        self._chain_id = chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self._factory_address = AsyncWeb3.to_checksum_address(factory_address)

        factory_abi = _load_abi("NdaiEscrowFactory.sol")
        escrow_abi = _load_abi("NdaiEscrow.sol")

        self._factory = self._w3.eth.contract(
            address=self._factory_address, abi=factory_abi
        )
        self._escrow_abi = escrow_abi

    # ------------------------------------------------------------------
    # Static / pure helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_attestation_hash(pcr0: bytes, nonce: bytes, outcome: bytes) -> bytes:
        """Compute the on-chain attestation hash.

        Mirrors the Solidity:
            keccak256(abi.encodePacked(pcr0, nonce, outcome))

        Args:
            pcr0: 48-byte PCR0 measurement from the Nitro enclave.
            nonce: Arbitrary nonce bytes.
            outcome: Encoded outcome bytes.

        Returns:
            32-byte keccak256 digest.
        """
        digest: bytes = AsyncWeb3.solidity_keccak(
            ["bytes", "bytes", "bytes"], [pcr0, nonce, outcome]
        )
        return digest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _escrow_contract(self, escrow_address: str) -> Any:
        addr = AsyncWeb3.to_checksum_address(escrow_address)
        return self._w3.eth.contract(address=addr, abi=self._escrow_abi)

    async def _send_tx(
        self,
        fn: Any,
        private_key: str,
        value_wei: int = 0,
    ) -> str:
        """Build, sign, and broadcast a transaction; return the tx hash hex."""
        account: LocalAccount = Account.from_key(private_key)
        nonce = await self._w3.eth.get_transaction_count(account.address)
        gas_price = await self._w3.eth.gas_price

        tx_params: dict[str, Any] = {
            "chainId": self._chain_id,
            "from": account.address,
            "nonce": nonce,
            "gasPrice": gas_price,
            "value": value_wei,
        }

        gas_estimate = await fn.estimate_gas(tx_params)
        tx_params["gas"] = int(gas_estimate * 1.2)  # 20% buffer

        raw_tx = await fn.build_transaction(tx_params)
        signed = account.sign_transaction(raw_tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info("Sent tx %s", tx_hash.hex())
        return tx_hash.hex()

    # ------------------------------------------------------------------
    # Factory interactions
    # ------------------------------------------------------------------

    async def create_deal(
        self,
        seller_address: str,
        operator_address: str,
        reserve_price_wei: int,
        deadline: int,
        budget_cap_wei: int,
        private_key: str,
    ) -> str:
        """Deploy a new NdaiEscrow via the factory.

        The factory uses msg.sender as the buyer internally, so no buyer
        address is passed here.

        Args:
            seller_address: Address of the deal seller.
            operator_address: Address of the TEE operator.
            reserve_price_wei: Minimum acceptable price in wei.
            deadline: Unix timestamp after which the deal may expire.
            budget_cap_wei: ETH value (in wei) sent as budgetCap.
            private_key: Hex private key of the funding account.

        Returns:
            Transaction hash hex string.
        """
        seller = AsyncWeb3.to_checksum_address(seller_address)
        operator = AsyncWeb3.to_checksum_address(operator_address)

        fn = self._factory.functions.createEscrow(
            seller, operator, reserve_price_wei, deadline
        )
        return await self._send_tx(fn, private_key, value_wei=budget_cap_wei)

    # ------------------------------------------------------------------
    # Escrow interactions
    # ------------------------------------------------------------------

    async def submit_outcome(
        self,
        escrow_address: str,
        final_price_wei: int,
        attestation_hash: bytes,
        private_key: str,
    ) -> str:
        """Submit the negotiation outcome (operator only).

        Args:
            escrow_address: Address of the deployed NdaiEscrow.
            final_price_wei: Agreed price in wei.
            attestation_hash: 32-byte keccak256 from compute_attestation_hash.
            private_key: Operator private key.

        Returns:
            Transaction hash hex string.
        """
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.submitOutcome(final_price_wei, attestation_hash)
        return await self._send_tx(fn, private_key)

    async def accept_deal(self, escrow_address: str, private_key: str) -> str:
        """Accept the submitted outcome (buyer only).

        Args:
            escrow_address: Address of the deployed NdaiEscrow.
            private_key: Buyer private key.

        Returns:
            Transaction hash hex string.
        """
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.acceptDeal()
        return await self._send_tx(fn, private_key)

    async def reject_deal(self, escrow_address: str, private_key: str) -> str:
        """Reject the submitted outcome (buyer only).

        Args:
            escrow_address: Address of the deployed NdaiEscrow.
            private_key: Buyer private key.

        Returns:
            Transaction hash hex string.
        """
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.rejectDeal()
        return await self._send_tx(fn, private_key)

    async def claim_expired(self, escrow_address: str, private_key: str) -> str:
        """Reclaim funds after deadline expiry (buyer only).

        Args:
            escrow_address: Address of the deployed NdaiEscrow.
            private_key: Buyer private key.

        Returns:
            Transaction hash hex string.
        """
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.claimExpired()
        return await self._send_tx(fn, private_key)

    # ------------------------------------------------------------------
    # Read-only queries
    # ------------------------------------------------------------------

    async def get_deal_state(self, escrow_address: str) -> DealState:
        """Fetch all deal state fields in parallel.

        Args:
            escrow_address: Address of the deployed NdaiEscrow.

        Returns:
            Populated DealState dataclass.
        """
        contract = self._escrow_contract(escrow_address)
        addr = AsyncWeb3.to_checksum_address(escrow_address)

        (
            seller,
            buyer,
            operator,
            reserve_price,
            budget_cap,
            final_price,
            attestation_hash,
            deadline,
            raw_state,
            balance,
        ) = await asyncio.gather(
            contract.functions.seller().call(),
            contract.functions.buyer().call(),
            contract.functions.operator().call(),
            contract.functions.reservePrice().call(),
            contract.functions.budgetCap().call(),
            contract.functions.finalPrice().call(),
            contract.functions.attestationHash().call(),
            contract.functions.deadline().call(),
            contract.functions.state().call(),
            self._w3.eth.get_balance(addr),
        )

        return DealState(
            seller=seller,
            buyer=buyer,
            operator=operator,
            reserve_price_wei=int(reserve_price),
            budget_cap_wei=int(budget_cap),
            final_price_wei=int(final_price),
            attestation_hash=bytes(attestation_hash),
            deadline=int(deadline),
            state=EscrowState(int(raw_state)),
            balance_wei=int(balance),
        )

    async def verify_attestation(
        self,
        escrow_address: str,
        pcr0: bytes,
        nonce: bytes,
        outcome: bytes,
    ) -> bool:
        """Verify that the stored attestation hash matches recomputed inputs.

        Args:
            escrow_address: Address of the deployed NdaiEscrow.
            pcr0: 48-byte PCR0 measurement.
            nonce: Nonce bytes used during negotiation.
            outcome: Encoded outcome bytes.

        Returns:
            True if the hashes match, False otherwise.
        """
        deal = await self.get_deal_state(escrow_address)
        expected = self.compute_attestation_hash(pcr0, nonce, outcome)
        return deal.attestation_hash == expected
