"""Async web3.py wrapper for SeriousCustomer contract."""

import json
import logging
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from ndai.blockchain.models import SeriousCustomerInfo

logger = logging.getLogger(__name__)

_CONTRACTS_OUT = Path(__file__).resolve().parents[2] / "contracts" / "out"


def _load_abi(name: str) -> list[dict[str, Any]]:
    stem = name.split(".")[0]
    artifact_path = _CONTRACTS_OUT / name / f"{stem}.json"
    with artifact_path.open() as f:
        artifact = json.load(f)
    return artifact["abi"]


class SeriousCustomerClient:
    """Async client for SeriousCustomer contract."""

    def __init__(self, rpc_url: str, contract_address: str, chain_id: int = 84532) -> None:
        if not AsyncWeb3.is_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address!r}")

        self._chain_id = chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self._contract_address = AsyncWeb3.to_checksum_address(contract_address)

        abi = _load_abi("SeriousCustomer.sol")
        self._contract = self._w3.eth.contract(
            address=self._contract_address, abi=abi
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

    # ------------------------------------------------------------------
    # Read functions
    # ------------------------------------------------------------------

    async def is_serious_customer(self, address: str) -> bool:
        return await self._contract.functions.isSeriousCustomer(
            AsyncWeb3.to_checksum_address(address)
        ).call()

    async def get_deposit(self, address: str) -> int:
        return await self._contract.functions.depositOf(
            AsyncWeb3.to_checksum_address(address)
        ).call()

    async def has_been_refunded(self, address: str) -> bool:
        return await self._contract.functions.hasBeenRefunded(
            AsyncWeb3.to_checksum_address(address)
        ).call()

    async def get_info(self, address: str) -> SeriousCustomerInfo:
        addr = AsyncWeb3.to_checksum_address(address)
        is_sc = await self._contract.functions.isSeriousCustomer(addr).call()
        deposit = await self._contract.functions.depositOf(addr).call()
        refunded = await self._contract.functions.hasBeenRefunded(addr).call()
        return SeriousCustomerInfo(
            is_serious_customer=is_sc,
            deposit_wei=deposit,
            has_been_refunded=refunded,
        )

    async def get_min_deposit_wei(self) -> int:
        return await self._contract.functions.getMinDepositWei().call()

    async def get_latest_price(self) -> int:
        return await self._contract.functions.getLatestPrice().call()

    # ------------------------------------------------------------------
    # Write functions (operator)
    # ------------------------------------------------------------------

    async def refund_deposit(self, buyer_address: str, private_key: str) -> str:
        fn = self._contract.functions.refundDeposit(
            AsyncWeb3.to_checksum_address(buyer_address)
        )
        return await self._send_tx(fn, private_key)

    async def grant_serious_customer(self, address: str, private_key: str) -> str:
        fn = self._contract.functions.grantSeriousCustomer(
            AsyncWeb3.to_checksum_address(address)
        )
        return await self._send_tx(fn, private_key)
