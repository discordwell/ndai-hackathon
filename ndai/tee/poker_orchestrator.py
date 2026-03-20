"""Poker table orchestrator.

Unlike the negotiation orchestrator (one-shot), poker tables are long-lived.
In simulated mode, we run the enclave poker logic in-process.
In Nitro mode, we communicate via vsock.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

from ndai.config import Settings
from ndai.enclave.poker.actions import handle_poker_action
from ndai.enclave.poker.state import TableState

logger = logging.getLogger(__name__)


class PokerOrchestrator:
    """Manages poker table lifecycle and enclave communication."""

    def __init__(self, settings: Settings):
        self._settings = settings
        # In simulated mode, poker tables live in-process
        self._poker_tables: dict[str, TableState] = {}
        self._timeout_tasks: dict[str, asyncio.Task] = {}

    async def send_action(self, request: dict[str, Any]) -> dict[str, Any]:
        """Forward a poker action to the enclave (or in-process in simulated mode)."""
        if self._settings.tee_mode == "simulated":
            return handle_poker_action(request, self._poker_tables)
        else:
            # Nitro mode: forward via vsock
            # TODO: implement vsock forwarding for Nitro mode
            raise NotImplementedError("Nitro poker not yet implemented")

    async def verify_deposit(
        self,
        escrow_contract: str,
        wallet_address: str,
        expected_amount: int,
    ) -> bool:
        """Verify a player's on-chain deposit to the PokerTable contract.

        Returns True if the player's balance on-chain >= expected_amount.
        Falls back to True (trust mode) if blockchain is not configured.
        """
        if not self._settings.blockchain_enabled or not escrow_contract:
            logger.warning("Blockchain not enabled — skipping deposit verification")
            return True

        try:
            from ndai.blockchain.poker_client import PokerBlockchainClient
            client = PokerBlockchainClient(
                rpc_url=self._settings.base_sepolia_rpc_url,
                chain_id=self._settings.chain_id,
            )
            balance = await client.get_player_balance(escrow_contract, wallet_address)
            if balance < expected_amount:
                logger.warning(
                    "Deposit verification failed: on-chain=%d, expected=%d, player=%s",
                    balance, expected_amount, wallet_address,
                )
                return False
            return True
        except Exception as exc:
            logger.error("Deposit verification error: %s", exc)
            return False

    async def settle_hand(
        self,
        table_id: str,
        escrow_contract: str,
        hand_number: int,
        stack_updates: dict[str, int],
        previous_stacks: dict[str, int],
        wallet_map: dict[str, str],
    ) -> str | None:
        """Settle a completed hand on-chain.

        Computes winner/loser deltas from stack_updates vs previous_stacks,
        then calls PokerTable.settleHand().

        Returns tx_hash on success, None if blockchain is disabled.
        """
        if not self._settings.blockchain_enabled or not escrow_contract:
            return None

        try:
            from ndai.blockchain.poker_client import PokerBlockchainClient

            # Compute deltas
            winners: list[str] = []
            win_amounts: list[int] = []
            losers: list[str] = []
            loss_amounts: list[int] = []

            for player_id, new_stack in stack_updates.items():
                old_stack = previous_stacks.get(player_id, 0)
                delta = new_stack - old_stack
                wallet = wallet_map.get(player_id)
                if not wallet:
                    continue
                if delta > 0:
                    winners.append(wallet)
                    win_amounts.append(delta)
                elif delta < 0:
                    losers.append(wallet)
                    loss_amounts.append(abs(delta))

            if not winners and not losers:
                return None  # No chip movement

            result_hash = hashlib.sha256(
                f"{table_id}:{hand_number}:{stack_updates}".encode()
            ).digest()

            client = PokerBlockchainClient(
                rpc_url=self._settings.base_sepolia_rpc_url,
                chain_id=self._settings.chain_id,
            )
            tx_hash = await client.settle_hand(
                table_address=escrow_contract,
                hand_number=hand_number,
                result_hash=result_hash,
                winners=winners,
                amounts=win_amounts,
                losers=losers,
                losses=loss_amounts,
                operator_key=self._settings.escrow_operator_key,
            )
            logger.info("Hand %d settled on-chain: tx=%s", hand_number, tx_hash)
            return tx_hash
        except Exception as exc:
            logger.error("On-chain settlement failed for hand %d: %s", hand_number, exc)
            return None

    async def start_timeout(
        self,
        table_id: str,
        seat_index: int,
        timeout_sec: int,
        callback,
    ) -> None:
        """Schedule an auto-fold if player doesn't act in time."""
        key = f"{table_id}:{seat_index}"
        self.cancel_timeout(table_id, seat_index)

        async def _timeout():
            await asyncio.sleep(timeout_sec)
            result = await self.send_action({
                "action": "poker_timeout",
                "table_id": table_id,
                "seat_index": seat_index,
            })
            if result.get("status") == "ok":
                await callback(table_id, result)

        task = asyncio.create_task(_timeout())
        self._timeout_tasks[key] = task

    def cancel_timeout(self, table_id: str, seat_index: int) -> None:
        """Cancel a pending timeout task."""
        key = f"{table_id}:{seat_index}"
        task = self._timeout_tasks.pop(key, None)
        if task and not task.done():
            task.cancel()

    def cancel_all_timeouts(self, table_id: str) -> None:
        """Cancel all timeouts for a table."""
        to_remove = [k for k in self._timeout_tasks if k.startswith(f"{table_id}:")]
        for key in to_remove:
            task = self._timeout_tasks.pop(key)
            if not task.done():
                task.cancel()


# Singleton orchestrator instance (created on first use)
_orchestrator: PokerOrchestrator | None = None


def get_poker_orchestrator() -> PokerOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        from ndai.config import settings
        _orchestrator = PokerOrchestrator(settings)
    return _orchestrator
