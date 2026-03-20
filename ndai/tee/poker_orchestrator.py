"""Poker table orchestrator.

Unlike the negotiation orchestrator (one-shot), poker tables are long-lived.
In simulated mode, we run the enclave poker logic in-process.
In Nitro mode, we communicate via vsock.
"""

from __future__ import annotations

import asyncio
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
