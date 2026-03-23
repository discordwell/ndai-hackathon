"""Poker table API endpoints with SSE streaming."""

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.poker import (
    CreateTableRequest,
    HandActionResponse,
    HandDetailResponse,
    HandSummaryResponse,
    JoinTableRequest,
    PlayerActionRequest,
    RebuyRequest,
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
# Per-table locks to prevent double hand starts
_table_locks: dict[str, asyncio.Lock] = {}
# Action sequence counters: "table_id:hand_number" -> next sequence
_action_sequence: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

async def _persist_hand_completion(
    table_id: str,
    events: list[dict],
    verification: dict | None = None,
    deck_seed_hash: str | None = None,
) -> None:
    """Persist all hand completion data to the PokerHand row."""
    hand_end = next((e for e in events if e.get("type") == "hand_end"), None)
    showdown = next((e for e in events if e.get("type") == "showdown"), None)
    if not hand_end:
        return

    hand_number = hand_end.get("hand_number", 0)
    if not hand_number:
        return

    try:
        async with async_session() as db:
            result = await db.execute(
                select(PokerHand).where(
                    PokerHand.table_id == uuid.UUID(table_id),
                    PokerHand.hand_number == hand_number,
                )
            )
            hand_row = result.scalar_one_or_none()
            if not hand_row:
                return

            # Community cards from showdown event or hand_end
            if showdown and showdown.get("community_cards"):
                hand_row.community_cards = showdown["community_cards"]
            else:
                # Collect from phase_change events
                for e in reversed(events):
                    if e.get("type") == "phase_change" and e.get("community_cards"):
                        hand_row.community_cards = e["community_cards"]
                        break

            # Pots awarded
            if showdown and showdown.get("results"):
                hand_row.pots_awarded = showdown["results"]
            elif hand_end.get("reason") == "last_standing":
                hand_row.pots_awarded = [{
                    "player_id": hand_end.get("winner_player_id", ""),
                    "amount": hand_end.get("amount", 0),
                    "hand_rank": "Last standing",
                }]

            # Deck seed hash
            hand_row.deck_seed_hash = deck_seed_hash or hand_end.get("deck_seed_hash")

            # Result hash
            stack_updates = hand_end.get("stack_updates", {})
            if stack_updates:
                hand_row.result_hash = hashlib.sha256(
                    f"{table_id}:{hand_number}:{stack_updates}".encode()
                ).hexdigest()

            # Verification data
            if verification:
                hand_row.verification_data = verification

            hand_row.ended_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:
        logger.warning("Failed to persist hand completion data for hand %d", hand_number)


async def _persist_action(
    table_id: str,
    hand_number: int,
    seat_index: int,
    player_id: str,
    phase: str,
    action: str,
    amount: int = 0,
) -> None:
    """Persist a single action to PokerHandAction."""
    seq_key = f"{table_id}:{hand_number}"
    seq = _action_sequence.get(seq_key, 0)
    _action_sequence[seq_key] = seq + 1

    try:
        async with async_session() as db:
            result = await db.execute(
                select(PokerHand.id).where(
                    PokerHand.table_id == uuid.UUID(table_id),
                    PokerHand.hand_number == hand_number,
                )
            )
            hand_id = result.scalar_one_or_none()
            if not hand_id:
                return

            action_row = PokerHandAction(
                hand_id=hand_id,
                seat_index=seat_index,
                player_id=uuid.UUID(player_id),
                phase=phase,
                action=action,
                amount=amount,
                sequence=seq,
            )
            db.add(action_row)
            await db.commit()
    except Exception:
        logger.warning("Failed to persist action for hand %d seq %d", hand_number, seq)


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
    """Broadcast a list of enclave events to SSE subscribers.

    Showdown events are public (cards are revealed at showdown in standard poker).
    deal/cards_dealt events are filtered per-player.
    """
    for event in events:
        event_type = event.get("type", "game_event")
        # Per-player filtering only for card dealing
        hands = player_hands if event_type == "cards_dealt" else None
        await _emit_poker_event(table_id, event_type, event, hands)


async def _handle_timeout_callback(table_id: str, result: dict) -> None:
    """Called when a player times out. Broadcasts the resulting events."""
    events = result.get("events", [])
    if events:
        await _broadcast_events(table_id, events)

    # Persist the timeout action
    for e in events:
        if e.get("type") == "player_timeout":
            seat_idx = e.get("seat")
            # Get table view to find player_id and phase
            view = result.get("table_view", {})
            phase = view.get("phase", "preflop")
            hand_number = view.get("hand_number", 0)
            seat_data = view.get("seats", [None] * 9)
            pid = seat_data[seat_idx]["player_id"] if seat_idx is not None and seat_data[seat_idx] else "unknown"
            if hand_number and pid != "unknown":
                await _persist_action(table_id, hand_number, seat_idx, pid, phase, "timeout_fold", 0)

    # Check if timeout caused hand to end
    if result.get("hand_over") or any(e.get("type") == "hand_end" for e in events):
        # Broadcast verification if present
        verification = result.get("verification")
        if verification:
            await _emit_poker_event(table_id, "hand_verification", {
                "verification": verification,
                "deck_seed_hash": result.get("deck_seed_hash", ""),
            })
        await _persist_hand_completion(
            table_id, events,
            verification=result.get("verification"),
            deck_seed_hash=result.get("deck_seed_hash"),
        )
        await _settle_and_continue(table_id, events)
    else:
        await _maybe_start_next_hand(table_id)


async def _settle_and_continue(table_id: str, events: list[dict]) -> None:
    """Settle the completed hand on-chain, then start the next hand."""
    orchestrator = get_poker_orchestrator()

    # Extract settlement data from hand_end event
    hand_end = next((e for e in events if e.get("type") == "hand_end"), None)
    if hand_end:
        stack_updates = hand_end.get("stack_updates", {})
        hand_number = hand_end.get("hand_number", 0)

        # Get table info for escrow contract and wallet addresses
        table_result = await orchestrator.send_action({
            "action": "poker_get_table",
            "table_id": table_id,
        })
        if table_result.get("status") == "ok":
            view = table_result.get("table_view", {})
            escrow = view.get("escrow_contract", "")
            # Build wallet map from seats
            wallet_map = {}
            previous_stacks = {}
            for seat in view.get("seats", []):
                if seat:
                    wallet_map[seat["player_id"]] = seat.get("wallet_address", "")
                    previous_stacks[seat["player_id"]] = seat.get("stack", 0)

            # Settle on-chain (non-blocking — failures are logged but don't block game)
            tx_hash = await orchestrator.settle_hand(
                table_id=table_id,
                escrow_contract=escrow,
                hand_number=hand_number,
                stack_updates=stack_updates,
                previous_stacks=previous_stacks,
                wallet_map=wallet_map,
            )

            if tx_hash:
                await _emit_poker_event(table_id, "settlement", {
                    "hand_number": hand_number,
                    "tx_hash": tx_hash,
                })

                # Update DB hand record with settlement tx
                try:
                    async with async_session() as db:
                        result = await db.execute(
                            select(PokerHand).where(
                                PokerHand.table_id == uuid.UUID(table_id),
                                PokerHand.hand_number == hand_number,
                            )
                        )
                        hand = result.scalar_one_or_none()
                        if hand:
                            hand.settlement_tx_hash = tx_hash
                            await db.commit()
                except Exception:
                    logger.warning("Failed to persist settlement tx hash")

    # Clean up action sequence counter
    if hand_end:
        seq_key = f"{table_id}:{hand_end.get('hand_number', 0)}"
        _action_sequence.pop(seq_key, None)

    await _maybe_start_next_hand(table_id)


def _get_table_lock(table_id: str) -> asyncio.Lock:
    if table_id not in _table_locks:
        _table_locks[table_id] = asyncio.Lock()
    return _table_locks[table_id]


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
        # Use lock to prevent double hand starts
        lock = _get_table_lock(table_id)
        if lock.locked():
            return
        async with lock:
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

    # If hand ended immediately (unlikely but possible), broadcast verification
    if result.get("verification"):
        await _emit_poker_event(table_id, "hand_verification", {
            "verification": result["verification"],
        })

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

    # Reset action sequence counter for new hand
    hand_number = result.get("hand_number")
    if hand_number:
        _action_sequence[f"{table_id}:{hand_number}"] = 0

    # Persist hand to DB
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
    """List open poker tables with player counts (single query)."""
    # Subquery for seat counts per table
    seat_counts = (
        select(
            PokerSeat.table_id,
            func.count(PokerSeat.id).label("player_count"),
        )
        .where(PokerSeat.status == "active")
        .group_by(PokerSeat.table_id)
        .subquery()
    )

    # Subquery for current user's seat at each table
    my_seats = (
        select(
            PokerSeat.table_id,
            PokerSeat.seat_index,
        )
        .where(
            PokerSeat.player_id == uuid.UUID(user_id),
            PokerSeat.status == "active",
        )
        .subquery()
    )

    result = await db.execute(
        select(
            PokerTable,
            func.coalesce(seat_counts.c.player_count, 0).label("player_count"),
            my_seats.c.seat_index.label("my_seat"),
        )
        .outerjoin(seat_counts, PokerTable.id == seat_counts.c.table_id)
        .outerjoin(my_seats, PokerTable.id == my_seats.c.table_id)
        .where(PokerTable.status.in_(["open", "running"]))
    )

    summaries = []
    for row in result:
        t = row[0]
        player_count = row[1]
        my_seat = row[2]
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
            my_seat=my_seat,
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

    # Verify on-chain deposit before seating
    # Look up escrow contract from DB
    table_row = await db.execute(
        select(PokerTable).where(PokerTable.id == uuid.UUID(table_id))
    )
    poker_table = table_row.scalar_one_or_none()
    escrow_addr = poker_table.escrow_contract if poker_table else None
    if escrow_addr:
        verified = await orchestrator.verify_deposit(escrow_addr, body.wallet_address, body.buy_in)
        if not verified:
            raise HTTPException(status_code=402, detail="On-chain deposit not verified")

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

    # Persist the player action to DB
    table_view = result.get("table_view", {})
    hand_number = table_view.get("hand_number", 0)
    phase = table_view.get("phase", "preflop")
    if hand_number:
        # Find the seat index from the player_action event
        for e in events:
            if e.get("type") == "player_action":
                await _persist_action(
                    table_id, hand_number, e.get("seat", 0),
                    user_id, phase, e.get("action", body.action),
                    e.get("amount", body.amount or 0),
                )
                break

    # If hand is over, broadcast verification and settle on-chain
    if result.get("hand_over"):
        # Broadcast verification chain to all players
        verification = result.get("verification")
        if verification:
            await _emit_poker_event(table_id, "hand_verification", {
                "verification": verification,
                "deck_seed_hash": result.get("deck_seed_hash", ""),
            })

        # Persist hand completion data
        await _persist_hand_completion(
            table_id, events,
            verification=result.get("verification"),
            deck_seed_hash=result.get("deck_seed_hash"),
        )

        task = asyncio.create_task(_settle_and_continue(table_id, events))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)

    return {"status": "ok", "events": events}


@router.post("/tables/{table_id}/start-hand")
async def start_hand_endpoint(
    table_id: str,
    user_id: str = Depends(get_current_user),
):
    """Manually start a new hand (if auto-start hasn't triggered)."""
    # Verify the requesting user is seated at this table
    orchestrator = get_poker_orchestrator()
    result = await orchestrator.send_action({
        "action": "poker_get_table",
        "table_id": table_id,
        "player_id": user_id,
    })
    if result.get("status") != "ok":
        raise HTTPException(status_code=404, detail="Table not found")
    view = result.get("table_view", {})
    if not any(s and s.get("player_id") == user_id for s in view.get("seats", [])):
        raise HTTPException(status_code=403, detail="Must be seated to start a hand")
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


@router.get("/tables/{table_id}/hands")
async def list_table_hands(
    table_id: str,
    limit: int = Query(default=20, le=100),
    before: int | None = Query(default=None),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List completed hands for a table, paginated by hand_number cursor."""
    query = (
        select(PokerHand, PokerTable.small_blind, PokerTable.big_blind)
        .join(PokerTable, PokerHand.table_id == PokerTable.id)
        .where(PokerHand.table_id == uuid.UUID(table_id))
    )

    if before is not None:
        query = query.where(PokerHand.hand_number < before)

    query = query.order_by(PokerHand.hand_number.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    hands = []
    for row in rows:
        h = row[0]
        hands.append(HandSummaryResponse(
            hand_number=h.hand_number,
            table_id=str(h.table_id),
            dealer_seat=h.dealer_seat,
            community_cards=h.community_cards,
            pots_awarded=h.pots_awarded,
            result_hash=h.result_hash,
            deck_seed_hash=h.deck_seed_hash,
            settlement_tx_hash=h.settlement_tx_hash,
            started_at=h.started_at.isoformat() if h.started_at else None,
            ended_at=h.ended_at.isoformat() if h.ended_at else None,
            small_blind=row[1],
            big_blind=row[2],
        ))

    return hands


@router.get("/tables/{table_id}/hands/{hand_number}")
async def get_hand_result(
    table_id: str,
    hand_number: int,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a completed hand result with action replay."""
    result = await db.execute(
        select(PokerHand).where(
            PokerHand.table_id == uuid.UUID(table_id),
            PokerHand.hand_number == hand_number,
        )
    )
    hand = result.scalar_one_or_none()
    if not hand:
        raise HTTPException(status_code=404, detail="Hand not found")

    # Fetch actions for this hand
    action_result = await db.execute(
        select(PokerHandAction)
        .where(PokerHandAction.hand_id == hand.id)
        .order_by(PokerHandAction.sequence)
    )
    actions = action_result.scalars().all()

    return HandDetailResponse(
        hand_number=hand.hand_number,
        table_id=str(hand.table_id),
        dealer_seat=hand.dealer_seat,
        community_cards=hand.community_cards,
        pots_awarded=hand.pots_awarded,
        result_hash=hand.result_hash,
        deck_seed_hash=hand.deck_seed_hash,
        settlement_tx_hash=hand.settlement_tx_hash,
        started_at=hand.started_at.isoformat() if hand.started_at else None,
        ended_at=hand.ended_at.isoformat() if hand.ended_at else None,
        actions=[
            HandActionResponse(
                seat_index=a.seat_index,
                player_id=str(a.player_id),
                phase=a.phase,
                action=a.action,
                amount=a.amount,
                sequence=a.sequence,
            )
            for a in actions
        ],
        verification=hand.verification_data,
    )


@router.post("/tables/{table_id}/rebuy")
async def rebuy(
    table_id: str,
    body: RebuyRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add chips to a seated player's stack between hands."""
    orchestrator = get_poker_orchestrator()

    # Verify player is seated
    result = await orchestrator.send_action({
        "action": "poker_get_table",
        "table_id": table_id,
        "player_id": user_id,
    })
    if result.get("status") != "ok":
        raise HTTPException(status_code=404, detail="Table not found")

    view = result.get("table_view", {})
    player_seat = None
    for s in view.get("seats", []):
        if s and s.get("player_id") == user_id:
            player_seat = s
            break

    if not player_seat:
        raise HTTPException(status_code=400, detail="Not seated at this table")

    # Only allow rebuy between hands
    phase = view.get("phase", "waiting")
    if phase not in ("waiting", "showdown", "settling"):
        raise HTTPException(status_code=400, detail="Can only rebuy between hands")

    # Validate amount
    new_stack = player_seat["stack"] + body.amount
    max_buy_in = view.get("max_buy_in", 0)
    if new_stack > max_buy_in:
        raise HTTPException(
            status_code=400,
            detail=f"Rebuy would exceed max buy-in ({max_buy_in}). Current stack: {player_seat['stack']}",
        )

    # Update the enclave state
    # We reuse the join action internally — the enclave handles stack updates
    # For now, directly update the in-process table state
    from ndai.enclave.poker.state import TableState
    poker_tables = orchestrator._poker_tables
    table = poker_tables.get(table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found in enclave")

    seat = table.player_by_id(user_id)
    if not seat:
        raise HTTPException(status_code=400, detail="Player not found in enclave")

    seat.stack += body.amount

    # Update DB
    seat_result = await db.execute(
        select(PokerSeat).where(
            PokerSeat.table_id == uuid.UUID(table_id),
            PokerSeat.player_id == uuid.UUID(user_id),
            PokerSeat.status == "active",
        )
    )
    db_seat = seat_result.scalar_one_or_none()
    if db_seat:
        db_seat.current_stack = seat.stack
        db_seat.buy_in += body.amount
        await db.commit()

    # Broadcast rebuy event
    await _emit_poker_event(table_id, "player_rebuy", {
        "player_id": user_id,
        "amount": body.amount,
        "new_stack": seat.stack,
    })

    return {"status": "ok", "new_stack": seat.stack}


@router.post("/tables/{table_id}/close")
async def close_table(
    table_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Close a table (creator only). All remaining players are cashed out."""
    # Verify user is the table creator
    table_row = await db.execute(
        select(PokerTable).where(PokerTable.id == uuid.UUID(table_id))
    )
    poker_table = table_row.scalar_one_or_none()
    if not poker_table:
        raise HTTPException(status_code=404, detail="Table not found")
    if str(poker_table.created_by) != user_id:
        raise HTTPException(status_code=403, detail="Only the table creator can close it")

    # Check no hand in progress
    orchestrator = get_poker_orchestrator()
    result = await orchestrator.send_action({
        "action": "poker_get_table",
        "table_id": table_id,
    })
    if result.get("status") == "ok":
        view = result.get("table_view", {})
        phase = view.get("phase", "waiting")
        if phase not in ("waiting", "showdown", "settling"):
            raise HTTPException(status_code=400, detail="Cannot close table while a hand is in progress")

    # Cancel all timeouts
    orchestrator.cancel_all_timeouts(table_id)

    # Mark all active seats as left
    seat_result = await db.execute(
        select(PokerSeat).where(
            PokerSeat.table_id == uuid.UUID(table_id),
            PokerSeat.status == "active",
        )
    )
    for seat in seat_result.scalars().all():
        seat.status = "left"
        seat.left_at = datetime.now(timezone.utc)

    # Close table in DB
    poker_table.status = "closed"
    poker_table.closed_at = datetime.now(timezone.utc)
    await db.commit()

    # Remove from enclave state
    if table_id in orchestrator._poker_tables:
        del orchestrator._poker_tables[table_id]

    # Clean up SSE queues and locks
    _table_queues.pop(table_id, None)
    _table_locks.pop(table_id, None)

    # Broadcast close event
    await _emit_poker_event(table_id, "table_closed", {"table_id": table_id})

    return {"status": "ok"}
