"""Demo-specific endpoints for the CVE-2024-3094 marketplace walkthrough.

These endpoints orchestrate the full verify → negotiate → seal pipeline
with SSE streaming for real-time progress updates. Separate from the
production vulns.py router to avoid polluting the main API.
"""

import asyncio
import json
import logging
import traceback
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_current_user
from ndai.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory state for demo pipeline
_pipeline_statuses: dict[str, dict] = {}
_progress_queues: dict[str, list[asyncio.Queue]] = {}
_tasks: set[asyncio.Task] = set()


class DemoPipelineRequest(BaseModel):
    """Request to start the full demo pipeline."""
    agreement_id: str
    budget_cap: float = 2.5
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    skip_verification: bool = False
    skip_sealed_delivery: bool = True  # Default true since we need buyer keys


class DemoPipelineStatus(BaseModel):
    """Status of a running or completed demo pipeline."""
    status: str  # pending, running, completed, error
    phase: str | None = None
    result: dict | None = None
    error: str | None = None


@router.post("/{agreement_id}/full-pipeline")
async def start_full_pipeline(
    agreement_id: str,
    request: DemoPipelineRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start the full demo pipeline: verify → negotiate → seal.

    Progress is streamed via SSE at GET /vuln-demo/{agreement_id}/progress.
    """
    if agreement_id in _pipeline_statuses and _pipeline_statuses[agreement_id].get("status") == "running":
        return {"status": "already_running"}

    from ndai.db.repositories import get_vuln_agreement, get_vulnerability

    agreement = await get_vuln_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

    vuln = await get_vulnerability(db, agreement.vulnerability_id)
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    _pipeline_statuses[agreement_id] = {"status": "pending", "phase": "initializing"}
    _progress_queues[agreement_id] = []

    async def _run_pipeline():
        try:
            _pipeline_statuses[agreement_id] = {"status": "running", "phase": "verification"}

            from ndai.config import settings
            from ndai.enclave.agents.base_agent import VulnerabilitySubmission
            from ndai.enclave.vuln_demo_session import DemoSessionConfig, VulnDemoSession

            # Build VulnerabilitySubmission from DB record
            vuln_submission = VulnerabilitySubmission(
                target_software=vuln.target_software,
                target_version=vuln.target_version,
                vulnerability_class=vuln.vulnerability_class,
                impact_type=vuln.impact_type,
                affected_component=vuln.affected_component or "",
                cvss_self_assessed=vuln.cvss_self_assessed,
                discovery_date=vuln.discovery_date,
                patch_status=vuln.patch_status,
                exclusivity=vuln.exclusivity,
                outside_option_value=vuln.outside_option_value or 0.5,
                max_disclosure_level=vuln.max_disclosure_level,
                software_category=vuln.software_category,
            )

            # Build TargetSpec from demo definition
            from demo.target_spec import create_xz_target_spec
            target_spec = create_xz_target_spec()

            config = DemoSessionConfig(
                target_spec=target_spec,
                vulnerability=vuln_submission,
                budget_cap=request.budget_cap,
                llm_provider=request.llm_provider,
                api_key=getattr(settings, "openai_api_key", "") or getattr(settings, "anthropic_api_key", ""),
                llm_model=request.llm_model,
                software_category=vuln.software_category,
                skip_verification=request.skip_verification,
                skip_sealed_delivery=request.skip_sealed_delivery,
            )

            def progress_callback(event: str, data: dict[str, Any]):
                _pipeline_statuses[agreement_id]["phase"] = event
                _broadcast_sse(agreement_id, event, data)

            session = VulnDemoSession(config, progress_callback=progress_callback)
            result = session.run()

            if result.success:
                result_data = {
                    "outcome": result.negotiation.outcome.value if result.negotiation else None,
                    "final_price": result.negotiation.final_price if result.negotiation else None,
                    "rounds": result.negotiation.negotiation_rounds if result.negotiation else None,
                }
                if result.verification:
                    result_data["verification"] = {
                        "claimed": result.verification.unpatched_capability.claimed.value,
                        "verified": result.verification.unpatched_capability.verified_level.value
                            if result.verification.unpatched_capability.verified_level else None,
                        "reliability": result.verification.unpatched_capability.reliability_score,
                    }
                _pipeline_statuses[agreement_id] = {
                    "status": "completed",
                    "phase": "done",
                    "result": result_data,
                }
                _broadcast_sse(agreement_id, "pipeline_complete", result_data)
            else:
                _pipeline_statuses[agreement_id] = {
                    "status": "error",
                    "phase": "error",
                    "error": result.error,
                }
                _broadcast_sse(agreement_id, "pipeline_error", {"error": result.error})

        except Exception:
            error_msg = traceback.format_exc()
            logger.error("Demo pipeline failed: %s", error_msg)
            _pipeline_statuses[agreement_id] = {
                "status": "error",
                "phase": "error",
                "error": error_msg[:500],
            }
            _broadcast_sse(agreement_id, "pipeline_error", {"error": error_msg[:200]})

    task = asyncio.create_task(_run_pipeline())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return {"status": "started", "agreement_id": agreement_id}


@router.get("/{agreement_id}/status")
async def get_pipeline_status(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get the current status of the demo pipeline."""
    status = _pipeline_statuses.get(agreement_id)
    if not status:
        raise HTTPException(status_code=404, detail="No pipeline found for this agreement")
    return DemoPipelineStatus(**status)


@router.get("/{agreement_id}/progress")
async def stream_progress(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
):
    """SSE stream of demo pipeline progress events."""
    queue: asyncio.Queue = asyncio.Queue()

    if agreement_id not in _progress_queues:
        _progress_queues[agreement_id] = []
    _progress_queues[agreement_id].append(queue)

    async def event_generator():
        try:
            # Send current status as first event
            status = _pipeline_statuses.get(agreement_id, {})
            yield f"data: {json.dumps({'event': 'status', **status})}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("event") in ("pipeline_complete", "pipeline_error"):
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'event': 'heartbeat'})}\n\n"
        finally:
            if agreement_id in _progress_queues:
                try:
                    _progress_queues[agreement_id].remove(queue)
                except ValueError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _broadcast_sse(agreement_id: str, event: str, data: dict):
    """Send an SSE event to all connected clients for this agreement."""
    queues = _progress_queues.get(agreement_id, [])
    message = {"event": event, **data}
    for queue in queues:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("SSE queue full for agreement %s", agreement_id)
