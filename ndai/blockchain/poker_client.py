"""Async web3.py client for PokerTable.sol and PokerTableFactory.sol.

Follows the same patterns as escrow_client.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eth_account import Account
from web3 import AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

CONTRACTS_OUT = Path(__file__).resolve().parent.parent.parent / "contracts" / "out"


@dataclass
class PokerTableState:
    operator: str
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    max_seats: int
    is_open: bool
    last_settled_hand: int
    player_count: int
    contract_balance: int


class PokerBlockchainClient:
    """Async client for PokerTable and PokerTableFactory contracts."""

    def __init__(self, rpc_url: str, factory_address: str = "", chain_id: int = 84532):
        self._w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
        self._w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self._chain_id = chain_id
        self._factory_address = AsyncWeb3.to_checksum_address(factory_address) if factory_address else None
        self._table_abi = self._load_abi("PokerTable.sol", "PokerTable")
        self._factory_abi = self._load_abi("PokerTableFactory.sol", "PokerTableFactory")

    @staticmethod
    def _load_abi(sol_file: str, contract_name: str) -> list[dict]:
        abi_path = CONTRACTS_OUT / sol_file / f"{contract_name}.json"
        if not abi_path.exists():
            logger.warning("ABI not found: %s (contracts may not be compiled)", abi_path)
            return []
        with open(abi_path) as f:
            data = json.load(f)
        return data.get("abi", [])

    def _table_contract(self, address: str):
        return self._w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(address),
            abi=self._table_abi,
        )

    def _factory_contract(self):
        if not self._factory_address:
            raise ValueError("Factory address not configured")
        return self._w3.eth.contract(
            address=self._factory_address,
            abi=self._factory_abi,
        )

    async def _send_tx(self, tx: dict, private_key: str) -> str:
        account = Account.from_key(private_key)
        tx["from"] = account.address
        tx["nonce"] = await self._w3.eth.get_transaction_count(account.address)
        tx["chainId"] = self._chain_id

        gas_estimate = await self._w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas_estimate * 1.2)
        tx["maxFeePerGas"] = await self._w3.eth.gas_price
        tx["maxPriorityFeePerGas"] = self._w3.to_wei(1, "gwei")

        signed = account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()

    # --- Factory methods ---

    async def create_table(
        self,
        small_blind: int,
        big_blind: int,
        min_buy_in: int,
        max_buy_in: int,
        max_seats: int,
        operator_key: str,
    ) -> str:
        """Deploy a new PokerTable via the factory. Returns tx hash."""
        contract = self._factory_contract()
        tx = await contract.functions.createTable(
            small_blind, big_blind, min_buy_in, max_buy_in, max_seats
        ).build_transaction({"value": 0})
        return await self._send_tx(tx, operator_key)

    # --- Table methods ---

    async def get_table_state(self, table_address: str) -> PokerTableState:
        """Fetch all table state in one call."""
        contract = self._table_contract(table_address)
        (operator, sb, bb, min_buy, max_buy, max_seats, is_open, last_hand, count, balance) = await asyncio.gather(
            contract.functions.operator().call(),
            contract.functions.smallBlind().call(),
            contract.functions.bigBlind().call(),
            contract.functions.minBuyIn().call(),
            contract.functions.maxBuyIn().call(),
            contract.functions.maxSeats().call(),
            contract.functions.isOpen().call(),
            contract.functions.lastSettledHand().call(),
            contract.functions.getPlayerCount().call(),
            self._w3.eth.get_balance(table_address),
        )
        return PokerTableState(
            operator=operator,
            small_blind=sb,
            big_blind=bb,
            min_buy_in=min_buy,
            max_buy_in=max_buy,
            max_seats=max_seats,
            is_open=is_open,
            last_settled_hand=last_hand,
            player_count=count,
            contract_balance=balance,
        )

    async def get_player_balance(self, table_address: str, player_address: str) -> int:
        contract = self._table_contract(table_address)
        return await contract.functions.getBalance(
            AsyncWeb3.to_checksum_address(player_address)
        ).call()

    async def settle_hand(
        self,
        table_address: str,
        hand_number: int,
        result_hash: bytes,
        winners: list[str],
        amounts: list[int],
        losers: list[str],
        losses: list[int],
        operator_key: str,
    ) -> str:
        """Settle a hand on-chain. Returns tx hash."""
        contract = self._table_contract(table_address)
        tx = await contract.functions.settleHand(
            hand_number,
            result_hash,
            [AsyncWeb3.to_checksum_address(w) for w in winners],
            amounts,
            [AsyncWeb3.to_checksum_address(l) for l in losers],
            losses,
        ).build_transaction({"value": 0})
        return await self._send_tx(tx, operator_key)

    async def close_table(self, table_address: str, operator_key: str) -> str:
        contract = self._table_contract(table_address)
        tx = await contract.functions.closeTable().build_transaction({"value": 0})
        return await self._send_tx(tx, operator_key)

    async def verify_hand_result(
        self, table_address: str, hand_number: int, expected_hash: bytes
    ) -> bool:
        contract = self._table_contract(table_address)
        return await contract.functions.verifyHandResult(hand_number, expected_hash).call()
