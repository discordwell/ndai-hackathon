"""Async web3.py wrapper for VulnEscrow and VulnEscrowFactory contracts."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from ndai.blockchain.models import VulnDealState, VulnEscrowState

logger = logging.getLogger(__name__)

_CONTRACTS_OUT = Path(__file__).resolve().parents[2] / "contracts" / "out"


def _load_abi(name: str) -> list[dict[str, Any]]:
    stem = name.split(".")[0]
    artifact_path = _CONTRACTS_OUT / name / f"{stem}.json"
    with artifact_path.open() as f:
        artifact = json.load(f)
    return artifact["abi"]


class VulnEscrowClient:
    """Async client for VulnEscrow/VulnEscrowFactory contracts."""

    def __init__(self, rpc_url: str, factory_address: str, chain_id: int = 84532) -> None:
        if not AsyncWeb3.is_address(factory_address):
            raise ValueError(f"Invalid factory address: {factory_address!r}")

        self._chain_id = chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self._factory_address = AsyncWeb3.to_checksum_address(factory_address)

        factory_abi = _load_abi("VulnEscrowFactory.sol")
        escrow_abi = _load_abi("VulnEscrow.sol")

        self._factory = self._w3.eth.contract(
            address=self._factory_address, abi=factory_abi
        )
        self._escrow_abi = escrow_abi

    def _escrow_contract(self, escrow_address: str) -> Any:
        return self._w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(escrow_address),
            abi=self._escrow_abi,
        )

    async def _send_tx(self, fn: Any, private_key: str, value_wei: int = 0) -> str:
        account: LocalAccount = Account.from_key(private_key)
        tx = await fn.build_transaction({
            "from": account.address,
            "value": value_wei,
            "nonce": await self._w3.eth.get_transaction_count(account.address),
            "chainId": self._chain_id,
            "gas": int(await fn.estimate_gas({"from": account.address, "value": value_wei}) * 1.2),
        })
        signed = account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt["transactionHash"].hex()

    @staticmethod
    def compute_attestation_hash(pcr0: bytes, nonce: bytes, outcome: bytes) -> bytes:
        return AsyncWeb3.solidity_keccak(["bytes32", "bytes32", "bytes32"], [pcr0, nonce, outcome])

    async def create_deal(
        self,
        seller_address: str,
        operator_address: str,
        reserve_price_wei: int,
        deadline: int,
        budget_cap_wei: int,
        discovery_timestamp: int,
        embargo_days: int,
        is_exclusive: bool,
        private_key: str,
    ) -> str:
        fn = self._factory.functions.createEscrow(
            AsyncWeb3.to_checksum_address(seller_address),
            AsyncWeb3.to_checksum_address(operator_address),
            reserve_price_wei,
            deadline,
            discovery_timestamp,
            embargo_days,
            is_exclusive,
        )
        return await self._send_tx(fn, private_key, value_wei=budget_cap_wei)

    async def submit_outcome(
        self,
        escrow_address: str,
        final_price_wei: int,
        attestation_hash: bytes,
        decay_numerator: int,
        private_key: str,
    ) -> str:
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.submitOutcome(final_price_wei, attestation_hash, decay_numerator)
        return await self._send_tx(fn, private_key)

    async def report_patch(self, escrow_address: str, private_key: str) -> str:
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.reportPatch()
        return await self._send_tx(fn, private_key)

    async def accept_deal(self, escrow_address: str, private_key: str) -> str:
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.acceptDeal()
        return await self._send_tx(fn, private_key)

    async def reject_deal(self, escrow_address: str, private_key: str) -> str:
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.rejectDeal()
        return await self._send_tx(fn, private_key)

    async def claim_expired(self, escrow_address: str, private_key: str) -> str:
        contract = self._escrow_contract(escrow_address)
        fn = contract.functions.claimExpired()
        return await self._send_tx(fn, private_key)

    async def get_deal_state(self, escrow_address: str) -> VulnDealState:
        c = self._escrow_contract(escrow_address)
        (
            seller, buyer, operator, reserve, budget, final_price,
            decay_adjusted, decay_num, att_hash, dl,
            discovery_ts, embargo_end, is_excl, is_patched, state_val, balance
        ) = await asyncio.gather(
            c.functions.seller().call(),
            c.functions.buyer().call(),
            c.functions.operator().call(),
            c.functions.reservePrice().call(),
            c.functions.budgetCap().call(),
            c.functions.finalPrice().call(),
            c.functions.decayAdjustedPrice().call(),
            c.functions.decayNumerator().call(),
            c.functions.attestationHash().call(),
            c.functions.deadline().call(),
            c.functions.discoveryTimestamp().call(),
            c.functions.embargoEndTimestamp().call(),
            c.functions.isExclusive().call(),
            c.functions.isPatchedBeforeSettlement().call(),
            c.functions.state().call(),
            self._w3.eth.get_balance(AsyncWeb3.to_checksum_address(escrow_address)),
        )
        return VulnDealState(
            seller=seller,
            buyer=buyer,
            operator=operator,
            reserve_price_wei=reserve,
            budget_cap_wei=budget,
            final_price_wei=final_price,
            decay_adjusted_price_wei=decay_adjusted,
            decay_numerator=decay_num,
            attestation_hash=att_hash,
            deadline=dl,
            discovery_timestamp=discovery_ts,
            embargo_end_timestamp=embargo_end,
            is_exclusive=is_excl,
            is_patched=is_patched,
            state=VulnEscrowState(state_val),
            balance_wei=balance,
        )

    async def verify_attestation(
        self, escrow_address: str, pcr0: bytes, nonce: bytes, outcome: bytes
    ) -> bool:
        c = self._escrow_contract(escrow_address)
        return await c.functions.verifyAttestation(pcr0, nonce, outcome).call()
