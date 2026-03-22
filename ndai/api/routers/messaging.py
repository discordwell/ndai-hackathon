"""E2E encrypted messaging endpoints.

The server is "platform blind" — it stores only ciphertext and public key
material. Messages are encrypted client-side using the Signal protocol
(X3DH + Double Ratchet). The server facilitates key exchange (prekey bundles)
and message relay (store + SSE push).
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_zk_identity, decode_zk_token
from ndai.api.schemas.messaging import (
    PrekeyBundleUpload,
    PrekeyBundleResponse,
    OTPKResponse,
    PrekeyStatusResponse,
    ConversationCreate,
    ConversationResponse,
    MessageSend,
    MessageResponse,
)
from ndai.db.session import get_db
from ndai.models.messaging import (
    MessagingPrekey,
    MessagingOTPK,
    MessagingConversation,
    MessagingMessage,
)

router = APIRouter()

# ─── Per-user SSE message queues (in-process) ──────────────────────────

_message_queues: dict[str, list[asyncio.Queue]] = {}


async def _push_to_user(pubkey: str, event_type: str, data: dict) -> None:
    """Push an SSE event to all connected tabs of a user."""
    queues = _message_queues.get(pubkey, [])
    payload = {"type": event_type, "data": data}
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # drop if client is too slow


# ─── Prekey Management ──────────────────────────────────────────────────


@router.post("/prekeys", status_code=201)
async def upload_prekeys(
    body: PrekeyBundleUpload,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Upload or update prekey bundle (called on registration and rotation)."""
    # Upsert prekey bundle
    existing = await db.execute(
        select(MessagingPrekey).where(MessagingPrekey.owner_pubkey == pubkey)
    )
    prekey = existing.scalar_one_or_none()

    if prekey:
        prekey.identity_x25519_pub = body.identity_x25519_pub
        prekey.signed_prekey_pub = body.signed_prekey_pub
        prekey.signed_prekey_sig = body.signed_prekey_sig
        prekey.signed_prekey_id = body.signed_prekey_id
        prekey.updated_at = datetime.now(timezone.utc)
    else:
        prekey = MessagingPrekey(
            owner_pubkey=pubkey,
            identity_x25519_pub=body.identity_x25519_pub,
            signed_prekey_pub=body.signed_prekey_pub,
            signed_prekey_sig=body.signed_prekey_sig,
            signed_prekey_id=body.signed_prekey_id,
        )
        db.add(prekey)

    # Insert new one-time prekeys
    for otpk in body.one_time_prekeys:
        db.add(MessagingOTPK(
            owner_pubkey=pubkey,
            otpk_pub=otpk.pub,
            otpk_index=otpk.index,
        ))

    await db.commit()
    return {"status": "ok", "otpks_uploaded": len(body.one_time_prekeys)}


@router.get("/prekeys/status", response_model=PrekeyStatusResponse)
async def prekey_status(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Check own OTPK count and signed prekey age."""
    count_result = await db.execute(
        select(func.count()).select_from(MessagingOTPK).where(and_(
            MessagingOTPK.owner_pubkey == pubkey,
            MessagingOTPK.consumed == False,
        ))
    )
    remaining = count_result.scalar() or 0

    prekey_result = await db.execute(
        select(MessagingPrekey).where(MessagingPrekey.owner_pubkey == pubkey)
    )
    prekey = prekey_result.scalar_one_or_none()
    age_hours = 0.0
    if prekey and prekey.updated_at:
        delta = datetime.now(timezone.utc) - prekey.updated_at.replace(tzinfo=timezone.utc)
        age_hours = delta.total_seconds() / 3600

    return PrekeyStatusResponse(remaining_otpks=remaining, signed_prekey_age_hours=age_hours)


@router.get("/prekeys/{peer_pubkey}", response_model=PrekeyBundleResponse)
async def fetch_prekeys(
    peer_pubkey: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a peer's prekey bundle for X3DH. Atomically consumes one OTPK."""
    result = await db.execute(
        select(MessagingPrekey).where(MessagingPrekey.owner_pubkey == peer_pubkey)
    )
    prekey = result.scalar_one_or_none()
    if not prekey:
        raise HTTPException(status_code=404, detail="No prekey bundle found for this identity")

    # Atomically consume one OTPK
    otpk_result = await db.execute(
        select(MessagingOTPK)
        .where(and_(
            MessagingOTPK.owner_pubkey == peer_pubkey,
            MessagingOTPK.consumed == False,
        ))
        .order_by(MessagingOTPK.otpk_index)
        .limit(1)
        .with_for_update()
    )
    otpk = otpk_result.scalar_one_or_none()

    otpk_response = None
    if otpk:
        otpk.consumed = True
        otpk_response = OTPKResponse(pub=otpk.otpk_pub, index=otpk.otpk_index)
        await db.commit()

    return PrekeyBundleResponse(
        identity_pubkey=peer_pubkey,
        identity_x25519_pub=prekey.identity_x25519_pub,
        signed_prekey_pub=prekey.signed_prekey_pub,
        signed_prekey_sig=prekey.signed_prekey_sig,
        signed_prekey_id=prekey.signed_prekey_id,
        one_time_prekey=otpk_response,
    )


# ─── Conversations ──────────────────────────────────────────────────────


def _dm_conversation_id(a: str, b: str) -> uuid.UUID:
    """Deterministic conversation ID from two pubkeys."""
    sorted_keys = "".join(sorted([a, b]))
    h = hashlib.sha256(sorted_keys.encode()).hexdigest()
    return uuid.UUID(h[:32])


@router.post("/conversations", response_model=ConversationResponse)
async def create_or_get_conversation(
    body: ConversationCreate,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Create or retrieve a conversation (DM or deal-scoped)."""
    if body.agreement_id:
        # Deal-scoped chat
        conv_id = uuid.UUID(body.agreement_id)
        result = await db.execute(
            select(MessagingConversation).where(MessagingConversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            if pubkey not in (conv.participant_a, conv.participant_b):
                raise HTTPException(status_code=403, detail="Not a participant in this deal")
            return _conv_response(conv)

        # Need to determine the other participant from the agreement
        # For now, require peer_pubkey to be provided for deal chats too
        if not body.peer_pubkey:
            raise HTTPException(status_code=400, detail="peer_pubkey required for new deal conversations")

        conv = MessagingConversation(
            id=conv_id,
            type="deal",
            agreement_id=uuid.UUID(body.agreement_id),
            participant_a=min(pubkey, body.peer_pubkey),
            participant_b=max(pubkey, body.peer_pubkey),
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return _conv_response(conv)

    elif body.peer_pubkey:
        # DM conversation
        if body.peer_pubkey == pubkey:
            raise HTTPException(status_code=400, detail="Cannot message yourself")

        conv_id = _dm_conversation_id(pubkey, body.peer_pubkey)
        result = await db.execute(
            select(MessagingConversation).where(MessagingConversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            return _conv_response(conv)

        conv = MessagingConversation(
            id=conv_id,
            type="dm",
            participant_a=min(pubkey, body.peer_pubkey),
            participant_b=max(pubkey, body.peer_pubkey),
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return _conv_response(conv)

    else:
        raise HTTPException(status_code=400, detail="Provide peer_pubkey or agreement_id")


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the authenticated user."""
    result = await db.execute(
        select(MessagingConversation)
        .where(or_(
            MessagingConversation.participant_a == pubkey,
            MessagingConversation.participant_b == pubkey,
        ))
        .order_by(MessagingConversation.created_at.desc())
    )
    convs = result.scalars().all()
    return [_conv_response(c) for c in convs]


def _conv_response(conv: MessagingConversation) -> ConversationResponse:
    return ConversationResponse(
        id=str(conv.id),
        type=conv.type,
        agreement_id=str(conv.agreement_id) if conv.agreement_id else None,
        participant_a=conv.participant_a,
        participant_b=conv.participant_b,
        created_at=conv.created_at.isoformat() if conv.created_at else "",
    )


# ─── Messages ───────────────────────────────────────────────────────────


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: str,
    before: str | None = None,
    limit: int = Query(default=50, le=200),
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Fetch paginated message history (newest first)."""
    conv_uuid = uuid.UUID(conversation_id)

    # Verify participant
    conv_result = await db.execute(
        select(MessagingConversation).where(MessagingConversation.id == conv_uuid)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv or pubkey not in (conv.participant_a, conv.participant_b):
        raise HTTPException(status_code=403, detail="Not a participant")

    now = datetime.now(timezone.utc)
    query = (
        select(MessagingMessage)
        .where(and_(
            MessagingMessage.conversation_id == conv_uuid,
            MessagingMessage.expires_at > now,
        ))
        .order_by(MessagingMessage.created_at.desc())
        .limit(limit)
    )
    if before:
        query = query.where(MessagingMessage.created_at < datetime.fromisoformat(before))

    result = await db.execute(query)
    messages = result.scalars().all()
    return [_msg_response(m) for m in reversed(messages)]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    conversation_id: str,
    body: MessageSend,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Send an encrypted message. Server stores ciphertext only."""
    conv_uuid = uuid.UUID(conversation_id)

    # Verify participant
    conv_result = await db.execute(
        select(MessagingConversation).where(MessagingConversation.id == conv_uuid)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv or pubkey not in (conv.participant_a, conv.participant_b):
        raise HTTPException(status_code=403, detail="Not a participant")

    # Get next message index
    count_result = await db.execute(
        select(func.count()).select_from(MessagingMessage).where(and_(
            MessagingMessage.conversation_id == conv_uuid,
            MessagingMessage.sender_pubkey == pubkey,
        ))
    )
    message_index = count_result.scalar() or 0

    now = datetime.now(timezone.utc)
    msg = MessagingMessage(
        conversation_id=conv_uuid,
        sender_pubkey=pubkey,
        ciphertext=body.ciphertext,
        header=body.header,
        x3dh_header=body.x3dh_header,
        message_index=message_index,
        created_at=now,
        expires_at=now + timedelta(days=30),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    # Push to recipient via SSE
    recipient = conv.participant_b if pubkey == conv.participant_a else conv.participant_a
    await _push_to_user(recipient, "new_message", {
        "conversation_id": conversation_id,
        "message_id": str(msg.id),
        "sender_pubkey": pubkey,
        "header": body.header,
        "ciphertext": body.ciphertext,
        "x3dh_header": body.x3dh_header,
        "message_index": message_index,
        "created_at": msg.created_at.isoformat(),
    })

    return _msg_response(msg)


def _msg_response(msg: MessagingMessage) -> MessageResponse:
    return MessageResponse(
        id=str(msg.id),
        conversation_id=str(msg.conversation_id),
        sender_pubkey=msg.sender_pubkey,
        ciphertext=msg.ciphertext,
        header=msg.header,
        x3dh_header=msg.x3dh_header,
        message_index=msg.message_index,
        created_at=msg.created_at.isoformat() if msg.created_at else "",
    )


# ─── SSE Stream ─────────────────────────────────────────────────────────


@router.get("/stream")
async def message_stream(
    token: str = Query(..., description="ZK JWT token for SSE auth"),
):
    """Per-user global SSE stream for real-time message delivery."""
    pubkey = decode_zk_token(token)

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    if pubkey not in _message_queues:
        _message_queues[pubkey] = []
    _message_queues[pubkey].append(queue)

    async def event_generator():
        try:
            # Flush undelivered messages on connect (scoped DB session)
            from ndai.db.session import async_session
            async with async_session() as db:
                undelivered = await db.execute(
                    select(MessagingMessage)
                    .join(MessagingConversation)
                    .where(and_(
                        MessagingMessage.delivered_at.is_(None),
                        MessagingMessage.sender_pubkey != pubkey,
                        or_(
                            MessagingConversation.participant_a == pubkey,
                            MessagingConversation.participant_b == pubkey,
                        ),
                    ))
                    .order_by(MessagingMessage.created_at)
                )
                for msg in undelivered.scalars():
                    data = {
                        "conversation_id": str(msg.conversation_id),
                        "message_id": str(msg.id),
                        "sender_pubkey": msg.sender_pubkey,
                        "header": msg.header,
                        "ciphertext": msg.ciphertext,
                        "x3dh_header": msg.x3dh_header,
                        "message_index": msg.message_index,
                        "created_at": msg.created_at.isoformat(),
                    }
                    yield f"event: new_message\ndata: {json.dumps(data)}\n\n"
                    msg.delivered_at = datetime.now(timezone.utc)
                await db.commit()

                # Check prekey status
                otpk_count = await db.execute(
                    select(func.count()).select_from(MessagingOTPK).where(and_(
                        MessagingOTPK.owner_pubkey == pubkey,
                        MessagingOTPK.consumed == False,
                    ))
                )
                remaining = otpk_count.scalar() or 0
                if remaining < 5:
                    yield f"event: prekey_low\ndata: {json.dumps({'remaining': remaining})}\n\n"
            # DB session released here

            # Enter real-time loop (no DB session needed)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in _message_queues.get(pubkey, []):
                _message_queues[pubkey].remove(queue)
            if not _message_queues.get(pubkey):
                _message_queues.pop(pubkey, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
