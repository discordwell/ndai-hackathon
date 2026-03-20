"""Props API — meeting transcript processing via TEE."""

import asyncio
import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.api.schemas.transcripts import (
    AggregationRequest,
    AggregationResponse,
    TranscriptResponse,
    TranscriptSubmitRequest,
    TranscriptSummaryResponse,
)
from ndai.config import settings
from ndai.db.repositories_transcripts import (
    create_summary,
    create_transcript,
    get_summary_by_transcript,
    get_transcript,
    list_summaries_by_ids,
    list_transcripts_by_user,
    update_transcript_status,
)
from ndai.db.session import get_db
from ndai.enclave.agents.llm_client import LLMClient
from ndai.enclave.agents.openai_llm_client import OpenAILLMClient
from ndai.enclave.sessions.transcript_processor import TranscriptConfig, TranscriptProcessingSession
from ndai.services.audit import log_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=TranscriptResponse, status_code=201)
async def submit_transcript(
    req: TranscriptSubmitRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content_hash = hashlib.sha256(req.content.encode()).hexdigest()

    transcript = await create_transcript(
        db, submitter_id=uuid.UUID(user_id),
        title=req.title, content_hash=content_hash, team_name=req.team_name,
    )

    config = TranscriptConfig(
        transcript_text=req.content,
        title=req.title,
        team_name=req.team_name,
        llm_provider=settings.llm_provider,
        api_key=settings.openai_api_key if settings.llm_provider == "openai" else settings.anthropic_api_key,
        llm_model=settings.openai_model if settings.llm_provider == "openai" else settings.anthropic_model,
    )
    session = TranscriptProcessingSession(config)
    result = await asyncio.to_thread(session.run)

    if result.success:
        verification_store = {
            "policy_report": result.policy_report,
            "policy_constraints": result.policy_constraints,
            "egress_log": result.egress_log,
            "verification": result.verification,
        } if result.verification else None
        await create_summary(
            db, transcript_id=transcript.id,
            executive_summary=result.executive_summary,
            action_items=result.action_items,
            key_decisions=result.key_decisions,
            dependencies=result.dependencies,
            blockers=result.blockers,
            sentiment=result.sentiment,
            verification_data=verification_store,
        )
        await update_transcript_status(db, transcript, "completed")
    else:
        await update_transcript_status(db, transcript, "error")

    await log_event(
        db, None, "transcript_processed",
        actor_id=uuid.UUID(user_id),
        metadata={"transcript_id": str(transcript.id), "success": result.success},
    )

    return _to_response(transcript)


@router.get("/", response_model=list[TranscriptResponse])
async def list_transcripts(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transcripts = await list_transcripts_by_user(db, uuid.UUID(user_id))
    return [_to_response(t) for t in transcripts]


@router.get("/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript_detail(
    transcript_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transcript = await get_transcript(db, uuid.UUID(transcript_id))
    if not transcript:
        raise HTTPException(404, "Transcript not found")
    if str(transcript.submitter_id) != user_id:
        raise HTTPException(403, "Not your transcript")
    return _to_response(transcript)


@router.get("/{transcript_id}/summary", response_model=TranscriptSummaryResponse)
async def get_summary(
    transcript_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    transcript = await get_transcript(db, uuid.UUID(transcript_id))
    if not transcript:
        raise HTTPException(404, "Transcript not found")
    if str(transcript.submitter_id) != user_id:
        raise HTTPException(403, "Not your transcript")

    summary = await get_summary_by_transcript(db, uuid.UUID(transcript_id))
    if not summary:
        raise HTTPException(404, "Summary not yet available")

    vd = summary.verification_data or {}
    return TranscriptSummaryResponse(
        id=str(summary.id), transcript_id=str(summary.transcript_id),
        executive_summary=summary.executive_summary,
        action_items=summary.action_items, key_decisions=summary.key_decisions,
        dependencies=summary.dependencies, blockers=summary.blockers,
        sentiment=summary.sentiment, created_at=summary.created_at,
        policy_report=vd.get("policy_report"),
        policy_constraints=vd.get("policy_constraints"),
        egress_log=vd.get("egress_log"),
        verification=vd.get("verification"),
    )


@router.post("/aggregate", response_model=AggregationResponse)
async def aggregate_transcripts(
    req: AggregationRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        ids = [uuid.UUID(tid) for tid in req.transcript_ids]
    except ValueError:
        raise HTTPException(422, "Invalid UUID format in transcript_ids")

    # Verify ownership of all referenced transcripts
    for tid in ids:
        transcript = await get_transcript(db, tid)
        if not transcript:
            raise HTTPException(404, f"Transcript {tid} not found")
        if str(transcript.submitter_id) != user_id:
            raise HTTPException(403, f"Not authorized to aggregate transcript {tid}")

    summaries = await list_summaries_by_ids(db, ids)
    if len(summaries) < 2:
        raise HTTPException(400, "Need at least 2 completed transcripts to aggregate")

    summary_texts = []
    for s in summaries:
        summary_texts.append(
            f"Team summary: {s.executive_summary}\n"
            f"Action items: {json.dumps(s.action_items)}\n"
            f"Dependencies: {json.dumps(s.dependencies)}\n"
            f"Blockers: {json.dumps(s.blockers)}"
        )

    combined = "\n---\n".join(summary_texts)

    from ndai.enclave.egress import EgressAwareLLMClient, EgressLog
    from ndai.enclave.verification import SessionVerificationChain

    chain = SessionVerificationChain()
    egress_log = EgressLog()

    chain.record("session_start", {
        "transcript_count": len(summaries),
    }, "Aggregation session initialized")

    if settings.llm_provider == "openai":
        raw_client = OpenAILLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    else:
        raw_client = LLMClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    client = EgressAwareLLMClient(raw_client, egress_log)

    system_prompt = (
        "You are analyzing summaries from multiple team meetings inside a TEE. "
        "Identify cross-team patterns and return ONLY valid JSON:\n"
        "{\n"
        '  "cross_team_summary": "2-3 sentence overview",\n'
        '  "shared_dependencies": ["dependency shared across teams"],\n'
        '  "shared_blockers": ["blocker affecting multiple teams"],\n'
        '  "recommendations": ["actionable recommendation"]\n'
        "}"
    )

    def _do_llm():
        response = client.create_message(
            system=system_prompt,
            messages=[{"role": "user", "content": combined}],
        )
        return client.extract_text(response)

    raw = await asyncio.to_thread(_do_llm)
    chain.record("llm_call", {"model": client.model}, "LLM called for cross-team aggregation")
    cleaned = raw.strip().strip("`").strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = {"cross_team_summary": raw[:500], "shared_dependencies": [], "shared_blockers": [], "recommendations": []}

    chain.record("result_produced", {"success": True}, "Aggregation result produced")
    report = chain.finalize()

    await log_event(db, None, "aggregation_completed", actor_id=uuid.UUID(user_id),
                    metadata={"transcript_count": len(summaries)})

    return AggregationResponse(
        cross_team_summary=data.get("cross_team_summary", ""),
        shared_dependencies=data.get("shared_dependencies", []),
        shared_blockers=data.get("shared_blockers", []),
        recommendations=data.get("recommendations", []),
        transcript_count=len(summaries),
        verification=report.to_dict(),
    )


def _to_response(t) -> TranscriptResponse:
    return TranscriptResponse(
        id=str(t.id), title=t.title, team_name=t.team_name,
        status=t.status, content_hash=t.content_hash, created_at=t.created_at,
    )
