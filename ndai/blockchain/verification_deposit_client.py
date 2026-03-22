"""Async web3.py wrapper for VerificationDeposit contract."""

import json
import logging
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from ndai.blockchain.models import DepositInfo, VerificationDepositState

logger = logging.getLogger(__name__)

_CONTRACTS_OUT = Path(__file__).resolve().parents[2] / "contracts" / "out"


def _load_abi(name: str) -> list[dict[str, Any]]:
    stem = name.split(".")[0]
    artifact_path = _CONTRACTS_OUT / name / f"{stem}.json"
    with artifact_path.open() as f:
        artifact = json.load(f)
    return artifact["abi"]


class VerificationDepositClient:
    """Async client for VerificationDeposit contract."""

    def __init__(self, rpc_url: str, contract_address: str, chain_id: int = 84532) -> None:
        if not AsyncWeb3.is_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address!r}")

        self._chain_id = chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self._contract_address = AsyncWeb3.to_checksum_address(contract_address)

        abi = _load_abi("VerificationDeposit.sol")
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

    async def get_deposit(self, proposal_id: bytes) -> DepositInfo:
        """Return the deposit info for the given proposal ID."""
        result = await self._contract.functions.deposits(proposal_id).call()
        return DepositInfo(
            seller=result[0],
            amount=result[1],
            settled=result[2],
        )

    async def has_badge(self, address: str) -> bool:
        """Return whether the address holds a verified-seller badge."""
        return await self._contract.functions.hasBadge(
            AsyncWeb3.to_checksum_address(address)
        ).call()

    async def get_platform_escrow(self, platform_key: bytes) -> int:
        """Return the platform escrow amount for the given platform key."""
        return await self._contract.functions.platformEscrow(platform_key).call()

    # ------------------------------------------------------------------
    # Write functions (operator)
    # ------------------------------------------------------------------

    async def refund(self, proposal_id: bytes, private_key: str) -> str:
        """Operator refunds the deposit back to the seller."""
        fn = self._contract.functions.refund(proposal_id)
        return await self._send_tx(fn, private_key)

    async def forfeit(self, proposal_id: bytes, private_key: str) -> str:
        """Operator forfeits the deposit (e.g. seller submitted fraudulent data)."""
        fn = self._contract.functions.forfeit(proposal_id)
        return await self._send_tx(fn, private_key)

    async def grant_badge(self, seller_address: str, private_key: str) -> str:
        """Operator grants a verified-seller badge to the address."""
        fn = self._contract.functions.grantBadge(
            AsyncWeb3.to_checksum_address(seller_address)
        )
        return await self._send_tx(fn, private_key)

    async def set_platform_escrow(
        self, platform_key: bytes, amount: int, private_key: str
    ) -> str:
        """Operator sets the required escrow amount for a platform key."""
        fn = self._contract.functions.setPlatformEscrow(platform_key, amount)
        return await self._send_tx(fn, private_key)

    async def withdraw_platform_fees(self, private_key: str) -> str:
        """Operator withdraws accumulated platform fees."""
        fn = self._contract.functions.withdrawPlatformFees()
        return await self._send_tx(fn, private_key)

    # ------------------------------------------------------------------
    # Write functions (seller)
    # ------------------------------------------------------------------

    async def deposit(
        self, proposal_id: bytes, private_key: str, value_wei: int
    ) -> str:
        """Seller places a verification deposit for a proposal."""
        fn = self._contract.functions.deposit(proposal_id)
        return await self._send_tx(fn, private_key, value_wei=value_wei)

    async def purchase_badge(self, private_key: str, value_wei: int) -> str:
        """Seller purchases a verified-seller badge."""
        fn = self._contract.functions.purchaseBadge()
        return await self._send_tx(fn, private_key, value_wei=value_wei)
