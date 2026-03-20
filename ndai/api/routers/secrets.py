"""Conditional Recall API — credential proxy via TEE."""

import asyncio
import base64
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.secrets import (
    SecretAccessLogResponse,
    SecretCreateRequest,
    SecretResponse,
    SecretUseRequest,
    SecretUseResponse,
)
from ndai.config import settings
from ndai.db.repositories_secrets import (
    create_access_log,
    create_secret,
    get_secret,
    list_access_logs,
    list_available_secrets,
    list_secrets_by_owner,
    try_claim_use,
)
from ndai.db.session import get_db
from ndai.enclave.sessions.secret_proxy import SecretProxyConfig, SecretProxySession
from ndai.services.audit import log_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=SecretResponse, status_code=201)
async def create_secret_endpoint(
    req: SecretCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    encoded = base64.b64encode(req.secret_value.encode()).decode()
    secret = await create_secret(
        db,
        owner_id=uuid.UUID(user_id),
        name=req.name,
        encrypted_value=encoded,
        policy=req.policy.model_dump(),
        description=req.description,
    )
    await log_event(db, None, "secret_created", actor_id=uuid.UUID(user_id),
                    metadata={"secret_id": str(secret.id), "name": req.name})
    return _to_response(secret, is_owner=True)


@router.get("/", response_model=list[SecretResponse])
async def list_my_secrets(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secrets = await list_secrets_by_owner(db, uuid.UUID(user_id))
    return [_to_response(s, is_owner=True) for s in secrets]


@router.get("/available", response_model=list[SecretResponse])
async def list_available(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secrets = await list_available_secrets(db)
    uid = uuid.UUID(user_id)
    return [_to_response(s, is_owner=(s.owner_id == uid)) for s in secrets]


@router.get("/{secret_id}", response_model=SecretResponse)
async def get_secret_detail(
    secret_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = await get_secret(db, uuid.UUID(secret_id))
    if not secret:
        raise HTTPException(404, "Secret not found")
    return _to_response(secret, is_owner=(secret.owner_id == uuid.UUID(user_id)))


@router.post("/{secret_id}/use", response_model=SecretUseResponse)
async def use_secret(
    secret_id: str,
    req: SecretUseRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = await get_secret(db, uuid.UUID(secret_id))
    if not secret:
        raise HTTPException(404, "Secret not found")
    if secret.owner_id == uuid.UUID(user_id):
        raise HTTPException(403, "Owner cannot use their own secret")
    if secret.status != "active":
        raise HTTPException(400, f"Secret is {secret.status}")
    if secret.uses_remaining <= 0:
        raise HTTPException(400, "No uses remaining")

    # Atomically claim a use before running the session
    claimed = await try_claim_use(db, uuid.UUID(secret_id))
    if not claimed:
        raise HTTPException(409, "Secret use could not be claimed (concurrent request or depleted)")

    secret_value = base64.b64decode(secret.encrypted_value).decode()

    config = SecretProxyConfig(
        secret_value=secret_value,
        action=req.action,
        policy=secret.policy,
        llm_provider=settings.llm_provider,
        api_key=settings.openai_api_key if settings.llm_provider == "openai" else settings.anthropic_api_key,
        llm_model=settings.openai_model if settings.llm_provider == "openai" else settings.anthropic_model,
    )
    session = SecretProxySession(config)
    result = await asyncio.to_thread(session.run)

    log_status = "approved" if result.success else "denied"
    await create_access_log(
        db, uuid.UUID(secret_id), uuid.UUID(user_id),
        req.action, log_status, result.result_text[:500] if result.success else None,
    )

    await log_event(
        db, None, f"secret_use_{log_status}",
        actor_id=uuid.UUID(user_id),
        metadata={"secret_id": secret_id, "action": req.action},
    )

    return SecretUseResponse(
        action=req.action,
        result=result.result_text,
        success=result.success,
        secret_name=secret.name,
    )


@router.get("/{secret_id}/access-log", response_model=list[SecretAccessLogResponse])
async def get_access_log(
    secret_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    secret = await get_secret(db, uuid.UUID(secret_id))
    if not secret:
        raise HTTPException(404, "Secret not found")
    if str(secret.owner_id) != user_id:
        raise HTTPException(403, "Only the owner can view access logs")
    logs = await list_access_logs(db, uuid.UUID(secret_id))
    return [
        SecretAccessLogResponse(
            id=log.id,
            secret_id=str(log.secret_id),
            requester_id=str(log.requester_id),
            action_requested=log.action_requested,
            status=log.status,
            result_summary=log.result_summary,
            created_at=log.created_at,
        )
        for log in logs
    ]


def _to_response(secret, is_owner: bool = False) -> SecretResponse:
    return SecretResponse(
        id=str(secret.id),
        name=secret.name,
        description=secret.description,
        policy=secret.policy,
        uses_remaining=secret.uses_remaining,
        status=secret.status,
        created_at=secret.created_at,
        is_owner=is_owner,
    )
