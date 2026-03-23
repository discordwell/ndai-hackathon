"""Async web3.py wrapper for VulnAuction + VulnAuctionFactory contracts."""

import json
import logging
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from ndai.blockchain.models import AuctionInfo, AuctionState

logger = logging.getLogger(__name__)

_CONTRACTS_OUT = Path(__file__).resolve().parents[2] / "contracts" / "out"


def _load_abi(name: str) -> list[dict[str, Any]]:
    stem = name.split(".")[0]
    artifact_path = _CONTRACTS_OUT / name / f"{stem}.json"
    with artifact_path.open() as f:
        artifact = json.load(f)
    return artifact["abi"]


class AuctionClient:
    """Async client for VulnAuctionFactory + individual VulnAuction contracts."""

    def __init__(self, rpc_url: str, factory_address: str, chain_id: int = 84532) -> None:
        if not AsyncWeb3.is_address(factory_address):
            raise ValueError(f"Invalid factory address: {factory_address!r}")

        self._chain_id = chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self._factory_address = AsyncWeb3.to_checksum_address(factory_address)

        self._factory_abi = _load_abi("VulnAuctionFactory.sol")
        self._auction_abi = _load_abi("VulnAuction.sol")

        self._factory = self._w3.eth.contract(
            address=self._factory_address, abi=self._factory_abi
        )

    def _auction_contract(self, address: str):
        return self._w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(address), abi=self._auction_abi
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
    # Factory
    # ------------------------------------------------------------------

    async def create_auction(
        self,
        operator: str,
        reserve_price_wei: int,
        duration_sec: int,
        sc_only: bool,
        private_key: str,
    ) -> str:
        """Seller creates a new auction via factory. Returns tx hash."""
        fn = self._factory.functions.createAuction(
            AsyncWeb3.to_checksum_address(operator),
            reserve_price_wei,
            duration_sec,
            sc_only,
        )
        return await self._send_tx(fn, private_key)

    async def get_auctions(self) -> list[str]:
        return await self._factory.functions.getAuctions().call()

    async def auction_count(self) -> int:
        return await self._factory.functions.auctionCount().call()

    # ------------------------------------------------------------------
    # Auction reads
    # ------------------------------------------------------------------

    async def get_auction_info(self, auction_address: str) -> AuctionInfo:
        c = self._auction_contract(auction_address)
        return AuctionInfo(
            seller=await c.functions.seller().call(),
            reserve_price_wei=await c.functions.reservePrice().call(),
            end_time=await c.functions.endTime().call(),
            sc_only=await c.functions.scOnly().call(),
            state=AuctionState(await c.functions.state().call()),
            highest_bidder=await c.functions.highestBidder().call(),
            highest_bid_wei=await c.functions.highestBid().call(),
        )

    async def get_pending_returns(self, auction_address: str, bidder: str) -> int:
        c = self._auction_contract(auction_address)
        return await c.functions.pendingReturns(
            AsyncWeb3.to_checksum_address(bidder)
        ).call()

    # ------------------------------------------------------------------
    # Auction writes
    # ------------------------------------------------------------------

    async def place_bid(self, auction_address: str, private_key: str, value_wei: int) -> str:
        c = self._auction_contract(auction_address)
        fn = c.functions.bid()
        return await self._send_tx(fn, private_key, value_wei=value_wei)

    async def withdraw(self, auction_address: str, private_key: str) -> str:
        c = self._auction_contract(auction_address)
        fn = c.functions.withdraw()
        return await self._send_tx(fn, private_key)

    async def end_auction(self, auction_address: str, private_key: str) -> str:
        c = self._auction_contract(auction_address)
        fn = c.functions.endAuction()
        return await self._send_tx(fn, private_key)

    async def settle(self, auction_address: str, private_key: str) -> str:
        c = self._auction_contract(auction_address)
        fn = c.functions.settle()
        return await self._send_tx(fn, private_key)

    async def cancel(self, auction_address: str, private_key: str) -> str:
        c = self._auction_contract(auction_address)
        fn = c.functions.cancel()
        return await self._send_tx(fn, private_key)
