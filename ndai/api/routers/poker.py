"""Poker table API endpoints with SSE streaming."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.poker import (
    CreateTableRequest,
    JoinTableRequest,
    PlayerActionRequest,
    TableSummaryResponse,
)
from ndai.db.session import async_session, get_db
from ndai.models.poker import PokerHand, PokerHandAction, PokerSeat, PokerTable
from ndai.tee.poker_orchestrator import get_poker_orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)

# SSE queues: table_id -> {player_id -> Queue}
_table_queues: dict[str, dict[str, asyncio.Queue]] = {}
# Background tasks (prevent GC)
_tasks: set[asyncio.Task] = set()


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

async def _emit_poker_event(
    table_id: str,
    event_type: str,
    data: dict,
    player_hands: dict | None = None,
) -> None:
    """Broadcast a game event to all SSE subscribers, filtering per player."""
    queues = _table_queues.get(table_id, {})
    for player_id, queue in queues.items():
        filtered = {**data}
        if player_hands:
            filtered["your_hole_cards"] = player_hands.get(player_id)
        else:
            filtered.pop("player_hands", None)
        try:
            queue.put_nowait({"type": event_type, "data": filtered})
        except asyncio.QueueFull:
            logger.warning("SSE queue full for player %s at table %s", player_id, table_id)


async def _broadcast_events(table_id: str, events: list[dict], player_hands: dict | None = None) -> None:
    """Broadcast a list of enclave events to SSE subscribers."""
    for event in events:
        event_type = event.get("type", "game_event")
        await _emit_poker_event(table_id, event_type, event, player_hands if event_type == "cards_dealt" else None)


async def _handle_timeout_callback(table_id: str, result: dict) -> None:
    """Called when a player times out. Broadcasts the resulting events."""
    if result.get("events"):
        await _broadcast_events(table_id, result["events"])
    await _maybe_start_next_hand(table_id)


async def _maybe_start_next_hand(table_id: str) -> None:
    """Auto-start next hand after a delay if conditions are met."""
    orchestrator = get_poker_orchestrator()

    # Check if hand is over
    result = await orchestrator.send_action({
        "action": "poker_get_table",
        "table_id": table_id,
    })
    if result.get("status") != "ok":
        return

    view = result.get("table_view", {})
    phase = view.get("phase", "")

    # Count seated players
    seated = sum(1 for s in view.get("seats", []) if s is not None)
    if seated < 2:
        return

    if phase in ("waiting", "showdown", "settling") or (view.get("hand_number") is not None and phase == "waiting"):
        await asyncio.sleep(3)  # Brief pause between hands
        await _do_start_hand(table_id)


async def _do_start_hand(table_id: str) -> None:
    """Start a hand and broadcast events."""
    orchestrator = get_poker_orchestrator()
    result = await orchestrator.send_action({
        "action": "poker_start_hand",
        "table_id": table_id,
    })

    if result.get("status") != "ok":
        logger.warning("Failed to auto-start hand at table %s: %s", table_id, result.get("error"))
        return

    player_hands = result.get("player_hands", {})
    events = result.get("events", [])

    # Broadcast events (cards_dealt events get per-player filtering)
    await _broadcast_events(table_id, events, player_hands)

    # Also send each player their hole cards as a dedicated event
    for player_id, cards in player_hands.items():
        queues = _table_queues.get(table_id, {})
        q = queues.get(player_id)
        if q:
            try:
                q.put_nowait({"type": "deal_hole_cards", "data": {"hole_cards": cards}})
            except asyncio.QueueFull:
                pass

    # Set up timeout for first player
    _setup_action_timeout(table_id, events)

    # Persist hand to DB
    hand_number = result.get("hand_number")
    if hand_number:
        try:
            async with async_session() as db:
                # Find dealer seat from events
                dealer_seat = 0
                for e in events:
                    if e.get("type") == "hand_start":
                        dealer_seat = e.get("dealer_seat", 0)
                        break

                hand = PokerHand(
                    table_id=uuid.UUID(table_id),
                    hand_number=hand_number,
                    dealer_seat=dealer_seat,
                )
                db.add(hand)
                await db.commit()
        except Exception:
            logger.warning("Failed to persist poker hand start")


def _setup_action_timeout(table_id: str, events: list[dict]) -> None:
    """Set up a timeout task for the current action_on player."""
    orchestrator = get_poker_orchestrator()
    for event in events:
        if event.get("type") == "action_on":
            seat = event.get("seat")
            if seat is not None:
                task = asyncio.create_task(
                    orchestrator.start_timeout(
                        table_id, seat, 30, _handle_timeout_callback
                    )
                )
                _tasks.add(task)
                task.add_done_callback(_tasks.discard)
            break


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/tables", response_model=TableSummaryResponse)
async def create_table(
    body: CreateTableRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new poker table."""
    table_id = str(uuid.uuid4())
    orchestrator = get_poker_orchestrator()

    # Create table in enclave
    result = await orchestrator.send_action({
        "action": "poker_create_table",
        "table_id": table_id,
        "small_blind": body.small_blind,
        "big_blind": body.big_blind,
        "min_buy_in": body.min_buy_in,
        "max_buy_in": body.max_buy_in,
        "max_seats": body.max_seats,
        "action_timeout_sec": body.action_timeout_sec,
    })

    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create table"))

    # Persist to DB
    poker_table = PokerTable(
        id=uuid.UUID(table_id),
        small_blind=body.small_blind,
        big_blind=body.big_blind,
        min_buy_in=body.min_buy_in,
        max_buy_in=body.max_buy_in,
        max_seats=body.max_seats,
        action_timeout_sec=body.action_timeout_sec,
        status="open",
        created_by=uuid.UUID(user_id),
    )
    db.add(poker_table)
    await db.commit()

    return TableSummaryResponse(
        id=table_id,
        small_blind=body.small_blind,
        big_blind=body.big_blind,
        min_buy_in=body.min_buy_in,
        max_buy_in=body.max_buy_in,
        max_seats=body.max_seats,
        player_count=0,
        status="open",
    )


@router.get("/tables")
async def list_tables(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List open poker tables."""
    result = await db.execute(
        select(PokerTable).where(PokerTable.status.in_(["open", "running"]))
    )
    tables = result.scalars().all()

    summaries = []
    for t in tables:
        # Count active seats
        seat_result = await db.execute(
            select(PokerSeat).where(
                PokerSeat.table_id == t.id,
                PokerSeat.status == "active",
            )
        )
        player_count = len(seat_result.scalars().all())

        summaries.append(TableSummaryResponse(
            id=str(t.id),
            small_blind=t.small_blind,
            big_blind=t.big_blind,
            min_buy_in=t.min_buy_in,
            max_buy_in=t.max_buy_in,
            max_seats=t.max_seats,
            player_count=player_count,
            status=t.status,
            escrow_contract=t.escrow_contract,
        ))

    return summaries


@router.get("/tables/{table_id}")
async def get_table(
    table_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get table state (filtered for current user)."""
    orchestrator = get_poker_orchestrator()
    result = await orchestrator.send_action({
        "action": "poker_get_table",
        "table_id": table_id,
        "player_id": user_id,
    })

    if result.get("status") != "ok":
        raise HTTPException(status_code=404, detail=result.get("error", "Table not found"))

    return result.get("table_view")


@router.post("/tables/{table_id}/join")
async def join_table(
    table_id: str,
    body: JoinTableRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a poker table."""
    orchestrator = get_poker_orchestrator()

    # TODO: verify on-chain deposit via body.deposit_tx_hash

    result = await orchestrator.send_action({
        "action": "poker_join_table",
        "table_id": table_id,
        "player_id": user_id,
        "wallet_address": body.wallet_address,
        "buy_in": body.buy_in,
        "preferred_seat": body.preferred_seat,
    })

    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to join"))

    # Persist seat to DB
    seat = PokerSeat(
        table_id=uuid.UUID(table_id),
        seat_index=result["seat_index"],
        player_id=uuid.UUID(user_id),
        wallet_address=body.wallet_address,
        buy_in=body.buy_in,
        current_stack=body.buy_in,
        deposit_tx_hash=body.deposit_tx_hash or None,
    )
    db.add(seat)
    await db.commit()

    # Broadcast table update
    await _emit_poker_event(table_id, "player_joined", {
        "seat_index": result["seat_index"],
        "player_id": user_id,
    })

    return result


@router.post("/tables/{table_id}/leave")
async def leave_table(
    table_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Leave a poker table and cash out."""
    orchestrator = get_poker_orchestrator()
    orchestrator.cancel_all_timeouts(table_id)

    result = await orchestrator.send_action({
        "action": "poker_leave_table",
        "table_id": table_id,
        "player_id": user_id,
    })

    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to leave"))

    # Update DB seat
    seat_result = await db.execute(
        select(PokerSeat).where(
            PokerSeat.table_id == uuid.UUID(table_id),
            PokerSeat.player_id == uuid.UUID(user_id),
            PokerSeat.status == "active",
        )
    )
    seat = seat_result.scalar_one_or_none()
    if seat:
        seat.status = "left"
        seat.cashout_amount = result.get("cashout_amount", 0)
        seat.current_stack = 0
        seat.left_at = datetime.now(timezone.utc)
        await db.commit()

    # Broadcast
    await _emit_poker_event(table_id, "player_left", {"player_id": user_id})

    # Remove from SSE subscribers
    _table_queues.get(table_id, {}).pop(user_id, None)

    return result


@router.post("/tables/{table_id}/action")
async def submit_action(
    table_id: str,
    body: PlayerActionRequest,
    user_id: str = Depends(get_current_user),
):
    """Submit a player action (fold/check/call/bet/raise/all_in)."""
    orchestrator = get_poker_orchestrator()

    result = await orchestrator.send_action({
        "action": "poker_action",
        "table_id": table_id,
        "player_id": user_id,
        "hand_action": body.action,
        "amount": body.amount or 0,
    })

    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Invalid action"))

    events = result.get("events", [])

    # Cancel current timeout, set up next one
    orchestrator.cancel_all_timeouts(table_id)
    _setup_action_timeout(table_id, events)

    # Broadcast events
    await _broadcast_events(table_id, events)

    # If hand is over, auto-start next hand
    if result.get("hand_over"):
        task = asyncio.create_task(_maybe_start_next_hand(table_id))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)

    return {"status": "ok", "events": events}


@router.post("/tables/{table_id}/start-hand")
async def start_hand_endpoint(
    table_id: str,
    user_id: str = Depends(get_current_user),
):
    """Manually start a new hand (if auto-start hasn't triggered)."""
    await _do_start_hand(table_id)
    return {"status": "ok"}


@router.get("/tables/{table_id}/stream")
async def stream_table(
    table_id: str,
    token: str = Query(...),
):
    """SSE stream for real-time poker game events.

    Each player gets a filtered view — they only see their own hole cards.
    Token is passed as query param because EventSource doesn't support headers.
    """
    from ndai.api.dependencies import decode_token
    user_id = decode_token(token)

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    if table_id not in _table_queues:
        _table_queues[table_id] = {}
    _table_queues[table_id][user_id] = queue

    async def event_generator():
        try:
            # Send initial game state
            orchestrator = get_poker_orchestrator()
            result = await orchestrator.send_action({
                "action": "poker_get_table",
                "table_id": table_id,
                "player_id": user_id,
            })
            if result.get("status") == "ok":
                yield f"event: game_state\ndata: {json.dumps(result['table_view'])}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            queues = _table_queues.get(table_id, {})
            queues.pop(user_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tables/{table_id}/hands/{hand_number}")
async def get_hand_result(
    table_id: str,
    hand_number: int,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a completed hand result."""
    result = await db.execute(
        select(PokerHand).where(
            PokerHand.table_id == uuid.UUID(table_id),
            PokerHand.hand_number == hand_number,
        )
    )
    hand = result.scalar_one_or_none()
    if not hand:
        raise HTTPException(status_code=404, detail="Hand not found")

    return {
        "hand_number": hand.hand_number,
        "dealer_seat": hand.dealer_seat,
        "community_cards": hand.community_cards,
        "pots_awarded": hand.pots_awarded,
        "result_hash": hand.result_hash,
        "deck_seed_hash": hand.deck_seed_hash,
    }
