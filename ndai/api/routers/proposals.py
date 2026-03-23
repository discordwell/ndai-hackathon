"""Verification proposals — submit a PoC against a known target for verification."""

import asyncio
import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import decode_zk_token, get_zk_identity
from ndai.api.schemas.known_target import (
    DepositConfirmRequest,
    ProposalCreateRequest,
    ProposalDetailResponse,
    ProposalResponse,
)
from ndai.db.session import get_db, get_db_context
from ndai.models.known_target import KnownTarget
from ndai.models.verification_proposal import VerificationProposal
from ndai.models.zk_identity import VulnIdentity

router = APIRouter(prefix="", tags=["proposals"])
logger = logging.getLogger(__name__)

# Per-process verification state and SSE queues
_verification_statuses: dict[str, dict] = {}
_progress_queues: dict[str, list[asyncio.Queue]] = {}


def _compute_proposal_id(proposal_uuid: uuid.UUID) -> str:
    """Compute bytes32 proposal ID for on-chain contract from UUID."""
    return "0x" + hashlib.sha256(proposal_uuid.bytes).hexdigest()


def _usd_to_wei(usd: int) -> str:
    """Rough USD to wei conversion at ~$2500/ETH. Returns string for uint256."""
    eth = usd / 2500.0
    wei = int(eth * 10**18)
    return str(wei)


@router.post("/", response_model=ProposalResponse, status_code=201)
async def create_proposal(
    request: ProposalCreateRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Create a verification proposal against a known target."""
    # Validate target_id is a valid UUID
    try:
        target_uuid = uuid.UUID(request.target_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid target_id format")

    # Look up target
    target_result = await db.execute(
        select(KnownTarget).where(KnownTarget.id == target_uuid)
    )
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    if not target.is_active:
        raise HTTPException(status_code=400, detail="Target is not currently active")

    # Validate PoC script type matches target
    if target.poc_script_type != "manual" and request.poc_script_type != target.poc_script_type:
        raise HTTPException(
            status_code=400,
            detail=f"Target requires PoC type '{target.poc_script_type}', got '{request.poc_script_type}'",
        )

    # Check if seller has badge (skip deposit)
    identity_result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
    )
    identity = identity_result.scalar_one_or_none()
    has_badge = identity is not None and identity.has_badge

    proposal_id = uuid.uuid4()
    deposit_proposal_id = _compute_proposal_id(proposal_id)
    deposit_amount_wei = _usd_to_wei(target.escrow_amount_usd) if not has_badge else None

    # Handle sealed (encrypted) vs plaintext PoC
    import base64 as _b64
    import hashlib as _hl
    sealed_poc_bytes = None
    sealed_poc_hash = None
    if request.sealed_poc:
        sealed_poc_bytes = _b64.b64decode(request.sealed_poc)
        if len(sealed_poc_bytes) < 148:  # ECIES minimum: 120 (DER) + 12 (nonce) + 16 (tag)
            raise HTTPException(status_code=400, detail="sealed_poc too small to be valid ECIES ciphertext")
        sealed_poc_hash = _hl.sha256(sealed_poc_bytes).hexdigest()

    proposal = VerificationProposal(
        id=proposal_id,
        seller_pubkey=pubkey,
        target_id=target.id,
        target_version=target.current_version,
        poc_script=request.poc_script,
        sealed_poc=sealed_poc_bytes,
        sealed_poc_hash=sealed_poc_hash,
        poc_script_type=request.poc_script_type,
        claimed_capability=request.claimed_capability,
        reliability_runs=request.reliability_runs,
        asking_price_eth=request.asking_price_eth,
        deposit_required=not has_badge,
        deposit_amount_wei=deposit_amount_wei,
        deposit_proposal_id=deposit_proposal_id,
        status="queued" if has_badge else "pending_deposit",
    )
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    return ProposalResponse(
        id=str(proposal.id),
        seller_pubkey=proposal.seller_pubkey,
        target_id=str(proposal.target_id),
        target_name=target.display_name,
        target_version=proposal.target_version,
        poc_script_type=proposal.poc_script_type,
        claimed_capability=proposal.claimed_capability,
        reliability_runs=proposal.reliability_runs,
        asking_price_eth=proposal.asking_price_eth,
        deposit_required=proposal.deposit_required,
        deposit_amount_wei=proposal.deposit_amount_wei,
        deposit_proposal_id=proposal.deposit_proposal_id,
        status=proposal.status,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


@router.get("/", response_model=list[ProposalResponse])
async def list_my_proposals(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List proposals submitted by the authenticated identity."""
    result = await db.execute(
        select(VerificationProposal)
        .where(VerificationProposal.seller_pubkey == pubkey)
        .order_by(VerificationProposal.created_at.desc())
    )
    proposals = result.scalars().all()

    # Batch-load target names
    target_ids = {p.target_id for p in proposals}
    targets_result = await db.execute(
        select(KnownTarget).where(KnownTarget.id.in_(target_ids))
    )
    target_names = {t.id: t.display_name for t in targets_result.scalars().all()}

    return [
        ProposalResponse(
            id=str(p.id),
            seller_pubkey=p.seller_pubkey,
            target_id=str(p.target_id),
            target_name=target_names.get(p.target_id, ""),
            target_version=p.target_version,
            poc_script_type=p.poc_script_type,
            claimed_capability=p.claimed_capability,
            reliability_runs=p.reliability_runs,
            asking_price_eth=p.asking_price_eth,
            deposit_required=p.deposit_required,
            deposit_amount_wei=p.deposit_amount_wei,
            deposit_proposal_id=p.deposit_proposal_id,
            status=p.status,
            created_vuln_id=str(p.created_vuln_id) if p.created_vuln_id else None,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in proposals
    ]


@router.get("/{proposal_id}", response_model=ProposalDetailResponse)
async def get_proposal(
    proposal_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Get proposal detail (must be the submitter)."""
    try:
        proposal_uuid = uuid.UUID(proposal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal_id format")

    result = await db.execute(
        select(VerificationProposal).where(
            VerificationProposal.id == proposal_uuid
        )
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.seller_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get target name
    target_result = await db.execute(
        select(KnownTarget).where(KnownTarget.id == proposal.target_id)
    )
    target = target_result.scalar_one_or_none()

    return ProposalDetailResponse(
        id=str(proposal.id),
        seller_pubkey=proposal.seller_pubkey,
        target_id=str(proposal.target_id),
        target_name=target.display_name if target else "",
        target_version=proposal.target_version,
        poc_script_type=proposal.poc_script_type,
        claimed_capability=proposal.claimed_capability,
        reliability_runs=proposal.reliability_runs,
        asking_price_eth=proposal.asking_price_eth,
        deposit_required=proposal.deposit_required,
        deposit_amount_wei=proposal.deposit_amount_wei,
        deposit_proposal_id=proposal.deposit_proposal_id,
        status=proposal.status,
        created_vuln_id=str(proposal.created_vuln_id) if proposal.created_vuln_id else None,
        verification_result_json=proposal.verification_result_json,
        verification_chain_hash=proposal.verification_chain_hash,
        attestation_pcr0=proposal.attestation_pcr0,
        error_details=proposal.error_details,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


@router.post("/{proposal_id}/confirm-deposit", response_model=ProposalResponse)
async def confirm_deposit(
    proposal_id: str,
    request: DepositConfirmRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Confirm on-chain deposit for a proposal."""
    try:
        proposal_uuid = uuid.UUID(proposal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal_id format")

    # Use SELECT ... FOR UPDATE to prevent race conditions — two concurrent
    # confirm-deposit requests could otherwise both see "pending_deposit".
    result = await db.execute(
        select(VerificationProposal)
        .where(VerificationProposal.id == proposal_uuid)
        .with_for_update()
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.seller_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Not authorized")
    if proposal.status != "pending_deposit":
        raise HTTPException(status_code=400, detail=f"Proposal status is '{proposal.status}', expected 'pending_deposit'")

    proposal.deposit_tx_hash = request.tx_hash
    proposal.status = "queued"
    await db.commit()
    await db.refresh(proposal)

    # Get target name
    target_result = await db.execute(
        select(KnownTarget).where(KnownTarget.id == proposal.target_id)
    )
    target = target_result.scalar_one_or_none()

    return ProposalResponse(
        id=str(proposal.id),
        seller_pubkey=proposal.seller_pubkey,
        target_id=str(proposal.target_id),
        target_name=target.display_name if target else "",
        target_version=proposal.target_version,
        poc_script_type=proposal.poc_script_type,
        claimed_capability=proposal.claimed_capability,
        reliability_runs=proposal.reliability_runs,
        asking_price_eth=proposal.asking_price_eth,
        deposit_required=proposal.deposit_required,
        deposit_amount_wei=proposal.deposit_amount_wei,
        deposit_proposal_id=proposal.deposit_proposal_id,
        status=proposal.status,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


@router.post("/{proposal_id}/verify")
async def trigger_verification(
    proposal_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Trigger verification for a proposal. Requires deposit confirmed or badge."""
    try:
        proposal_uuid = uuid.UUID(proposal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal_id format")

    # Use SELECT ... FOR UPDATE to prevent race conditions on status transitions.
    # Two concurrent verify requests would otherwise both see "queued" and proceed.
    result = await db.execute(
        select(VerificationProposal)
        .where(VerificationProposal.id == proposal_uuid)
        .with_for_update()
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.seller_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Not authorized")
    if proposal.status != "queued":
        raise HTTPException(status_code=400, detail=f"Proposal status is '{proposal.status}', must be 'queued' to verify")

    # Look up target
    target_result = await db.execute(
        select(KnownTarget).where(KnownTarget.id == proposal.target_id)
    )
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target no longer exists")

    proposal.status = "building"
    await db.commit()

    # Compute commitment hash: SHA-256 of the sealed PoC (or plaintext PoC).
    # This is the "go code" — once emitted, the PoC is frozen.
    import hashlib as _hl
    poc_data = proposal.sealed_poc or (proposal.poc_script or "").encode()
    commitment_hash = _hl.sha256(poc_data if isinstance(poc_data, bytes) else poc_data.encode()).hexdigest()

    _verification_statuses[proposal_id] = {"status": "building"}
    await _emit_progress(proposal_id, "building", {
        "message": "Preparing verification environment...",
        "commitment_hash": commitment_hash,
        "sealed": proposal.sealed_poc is not None,
    })

    # Queue async verification in background with its own DB session.
    asyncio.create_task(_run_verification(str(proposal.id)))

    return {
        "status": "building",
        "message": "Verification started",
        "commitment_hash": commitment_hash,
    }


@router.get("/{proposal_id}/stream")
async def stream_verification(
    proposal_id: str,
    token: str = Query(..., description="ZK JWT token for SSE auth"),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for real-time verification progress."""
    pubkey = decode_zk_token(token)

    try:
        proposal_uuid = uuid.UUID(proposal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal_id format")

    result = await db.execute(
        select(VerificationProposal).where(
            VerificationProposal.id == proposal_uuid
        )
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.seller_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Not authorized")

    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    if proposal_id not in _progress_queues:
        _progress_queues[proposal_id] = []
    _progress_queues[proposal_id].append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['phase']}\ndata: {json.dumps(event['data'])}\n\n"
                    if event["phase"] in ("result", "error_event"):
                        break
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in _progress_queues.get(proposal_id, []):
                _progress_queues[proposal_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _emit_progress(proposal_id: str, phase: str, data: dict | None = None):
    """Emit an SSE event to all listeners for a given proposal."""
    queues = _progress_queues.get(proposal_id, [])
    event = {"phase": phase, "data": data or {}}
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def _run_verification(proposal_id: str):
    """Background task: run capability-oracle verification against a known target.

    In simulated mode, runs VulnVerificationProtocol directly in-process.
    In nitro mode, routes through VerificationDispatcher → NitroVerifier →
    VulnVerifyOrchestrator for real Nitro Enclave execution.

    Emits SSE events: building → build_done → verifying → verify_done → result | error_event
    """
    try:
        # 1. Load proposal + target
        async with get_db_context() as db:
            prop_result = await db.execute(
                select(VerificationProposal).where(
                    VerificationProposal.id == uuid.UUID(proposal_id)
                )
            )
            proposal = prop_result.scalar_one_or_none()
            if not proposal:
                raise RuntimeError(f"Proposal {proposal_id} not found")

            target_result = await db.execute(
                select(KnownTarget).where(KnownTarget.id == proposal.target_id)
            )
            target = target_result.scalar_one_or_none()
            if not target:
                raise RuntimeError(f"Target {proposal.target_id} not found")

            # Snapshot fields needed after session closes
            prop_claimed_capability = proposal.claimed_capability

        # 2. Route to appropriate verification backend
        from ndai.config import settings as app_settings

        await _emit_progress(proposal_id, "building", {"message": "Constructing target specification..."})
        _verification_statuses[proposal_id] = {"status": "building"}

        if app_settings.tee_mode == "nitro":
            # Full Nitro pipeline: EIF build → enclave launch → attestation → verify
            result_json, chain_hash, pcr0 = await _run_nitro_verification(
                proposal_id, proposal, target, prop_claimed_capability,
            )
        else:
            # Simulated: run protocol directly in-process
            result_json, chain_hash, pcr0 = await _run_simulated_verification(
                proposal_id, proposal, target, prop_claimed_capability,
            )

        passed = result_json.get("passed", False)

        # 3. Persist to DB + auto-create listing on pass
        async with get_db_context() as db:
            db_result = await db.execute(
                select(VerificationProposal)
                .where(VerificationProposal.id == uuid.UUID(proposal_id))
                .with_for_update()
            )
            prop = db_result.scalar_one_or_none()
            if prop:
                prop.status = "passed" if passed else "failed"
                prop.verification_result_json = result_json
                prop.verification_chain_hash = chain_hash
                prop.attestation_pcr0 = pcr0
                prop.error_details = None if passed else "Capability not verified by oracle"

                # Auto-create verified marketplace listing on pass
                if passed:
                    target_result = await db.execute(
                        select(KnownTarget).where(KnownTarget.id == prop.target_id)
                    )
                    t = target_result.scalar_one_or_none()
                    if t:
                        from ndai.models.zk_vulnerability import ZKVulnerability
                        listing = ZKVulnerability(
                            seller_pubkey=prop.seller_pubkey,
                            target_software=t.display_name,
                            target_version=t.current_version,
                            vulnerability_class=prop.claimed_capability.upper(),
                            impact_type=prop.claimed_capability.upper(),
                            cvss_self_assessed=7.0,  # Default for verified exploits
                            asking_price_eth=prop.asking_price_eth,
                            discovery_date=prop.created_at.strftime("%Y-%m-%d"),
                            anonymized_summary=f"Verified {prop.claimed_capability.upper()} capability against {t.display_name} v{t.current_version}. "
                                f"Reliability: {result_json.get('reliability_score', 0):.0%}. "
                                f"Attestation PCR0: {pcr0[:16]}... Chain hash: {chain_hash[:16]}...",
                            status="active",
                        )
                        db.add(listing)
                        prop.created_vuln_id = listing.id
                        logger.info("Auto-created verified listing %s for proposal %s", listing.id, proposal_id)

                    # Award badge on first successful verification
                    identity_result = await db.execute(
                        select(VulnIdentity).where(VulnIdentity.public_key == prop.seller_pubkey)
                    )
                    identity = identity_result.scalar_one_or_none()
                    if identity and not identity.has_badge:
                        from datetime import datetime, timezone
                        identity.has_badge = True
                        identity.badge_type = "earned"
                        identity.badge_awarded_at = datetime.now(timezone.utc)
                        logger.info("Awarded badge to %s on first verification pass", prop.seller_pubkey[:16])

                await db.commit()

        # 4. Emit terminal SSE events
        await _emit_progress(proposal_id, "verify_done", {"message": "Oracle checks complete."})
        await _emit_progress(proposal_id, "result", result_json)
        _verification_statuses[proposal_id] = {"status": "passed" if passed else "failed"}

        logger.info(
            "Verification complete for proposal %s: passed=%s pcr0=%s",
            proposal_id, passed, pcr0[:16] if pcr0 else "none",
        )

    except Exception as e:
        logger.exception("Verification failed for proposal %s", proposal_id)
        try:
            async with get_db_context() as db:
                db_result = await db.execute(
                    select(VerificationProposal)
                    .where(VerificationProposal.id == uuid.UUID(proposal_id))
                    .with_for_update()
                )
                prop = db_result.scalar_one_or_none()
                if prop:
                    prop.status = "failed"
                    prop.error_details = str(e)[:2000]
                    await db.commit()
        except Exception:
            logger.exception("Failed to persist error status for proposal %s", proposal_id)

        await _emit_progress(proposal_id, "error_event", {"message": str(e)})
        _verification_statuses[proposal_id] = {"status": "error", "error": str(e)}


async def _run_nitro_verification(proposal_id, proposal, target, claimed_capability):
    """Full Nitro pipeline: EIF build → enclave → attestation → oracle verification."""
    from ndai.services.verification_dispatcher import VerificationDispatcher

    async def progress_cb(phase, data):
        await _emit_progress(proposal_id, phase, data)

    dispatcher = VerificationDispatcher()
    outcome = await dispatcher.dispatch(proposal, target, progress_callback=progress_cb)

    passed = outcome.success
    result_json = {
        "claimed_capability": claimed_capability,
        "verified_capability": None,
        "reliability_score": 0.0,
        "passed": passed,
        "error": outcome.error,
    }
    if outcome.capability_result:
        result_json.update(outcome.capability_result)

    return result_json, outcome.chain_hash, outcome.pcr0 or "nitro"


async def _run_simulated_verification(proposal_id, proposal, target, claimed_capability):
    """Simulated mode: run VulnVerificationProtocol directly in-process."""
    from ndai.services.nitro_verifier import NitroVerifier
    verifier = NitroVerifier()
    target_spec = verifier.build_target_spec(target, proposal)

    # If sealed_poc, decrypt using the simulated enclave keypair
    if proposal.sealed_poc and not proposal.poc_script:
        from ndai.api.routers.enclave import _get_sim_state
        from ndai.enclave.ephemeral_keys import ecies_decrypt
        from dataclasses import replace as _dc_replace
        from ndai.enclave.vuln_verify.models import PoCSpec
        sim_keypair, _ = _get_sim_state()
        poc_plaintext = ecies_decrypt(sim_keypair.private_key, proposal.sealed_poc)
        # Replace the frozen PoCSpec with decrypted content
        target_spec = _dc_replace(target_spec, poc=PoCSpec(
            script_type=target_spec.poc.script_type,
            script_content=poc_plaintext.decode("utf-8"),
            timeout_sec=target_spec.poc.timeout_sec,
            run_as_user=target_spec.poc.run_as_user,
        ))
        logger.info("Decrypted sealed PoC (%d bytes) for proposal %s", len(poc_plaintext), proposal_id)

    await _emit_progress(proposal_id, "build_done", {"message": "Target specification ready."})

    from ndai.enclave.vuln_verify.protocol import VulnVerificationProtocol
    from ndai.enclave.vuln_verify.poc_executor import PoCExecutor
    from ndai.enclave.vuln_verify.oracles import OracleManager

    executor = PoCExecutor(enforce_rlimits=False)
    oracle = OracleManager()
    protocol = VulnVerificationProtocol(spec=target_spec, executor=executor, oracle=oracle)

    await _emit_progress(proposal_id, "verifying", {"message": "Running capability oracles..."})
    _verification_statuses[proposal_id] = {"status": "verifying"}

    result = await asyncio.wait_for(asyncio.to_thread(protocol.run), timeout=300)

    unpatched = result.unpatched_capability
    passed = unpatched is not None and unpatched.verified_level is not None

    result_json = {
        "claimed_capability": claimed_capability,
        "verified_capability": unpatched.verified_level.value if passed and unpatched.verified_level else None,
        "reliability_score": unpatched.reliability_score if unpatched else 0.0,
        "passed": passed,
        "error": None if passed else "Capability not verified by oracle",
    }
    return result_json, result.verification_chain_hash, "simulated"
