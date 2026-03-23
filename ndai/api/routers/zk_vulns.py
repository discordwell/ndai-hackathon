"""ZK-authenticated vulnerability marketplace endpoints."""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import decode_zk_token, get_zk_identity
from ndai.api.schemas.zk_vulnerability import (
    ZKVulnAgreementCreateRequest,
    ZKVulnAgreementResponse,
    ZKVulnCreateRequest,
    ZKVulnListingResponse,
    ZKVulnOutcomeResponse,
    ZKVulnResponse,
    ZKWalletConnectRequest,
)
from ndai.db.session import get_db
from ndai.models.zk_identity import VulnIdentity
from ndai.models.zk_vulnerability import ZKVulnAgreement, ZKVulnOutcome, ZKVulnerability

router = APIRouter(prefix="", tags=["zk-vulnerabilities"])
logger = logging.getLogger(__name__)

# Transient per-process negotiation state
_statuses: dict[str, dict] = {}
_progress_queues: dict[str, list[asyncio.Queue]] = {}


# ── Vulnerability CRUD ──


@router.post("/", response_model=ZKVulnResponse, status_code=201)
async def create_zk_vuln(
    request: ZKVulnCreateRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Submit a vulnerability for sale on the ZK marketplace."""
    vuln = ZKVulnerability(
        seller_pubkey=pubkey,
        **request.model_dump(),
    )
    db.add(vuln)
    await db.commit()
    await db.refresh(vuln)
    return ZKVulnResponse(
        id=str(vuln.id),
        seller_pubkey=vuln.seller_pubkey,
        target_software=vuln.target_software,
        target_version=vuln.target_version,
        vulnerability_class=vuln.vulnerability_class,
        impact_type=vuln.impact_type,
        cvss_self_assessed=vuln.cvss_self_assessed,
        asking_price_eth=vuln.asking_price_eth,
        patch_status=vuln.patch_status,
        exclusivity=vuln.exclusivity,
        serious_customers_only=vuln.serious_customers_only,
        status=vuln.status,
        created_at=vuln.created_at,
    )


@router.get("/", response_model=list[ZKVulnResponse])
async def list_my_zk_vulns(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List vulnerabilities submitted by the authenticated identity."""
    result = await db.execute(
        select(ZKVulnerability).where(ZKVulnerability.seller_pubkey == pubkey)
    )
    vulns = result.scalars().all()
    return [
        ZKVulnResponse(
            id=str(v.id),
            seller_pubkey=v.seller_pubkey,
            target_software=v.target_software,
            target_version=v.target_version,
            vulnerability_class=v.vulnerability_class,
            impact_type=v.impact_type,
            cvss_self_assessed=v.cvss_self_assessed,
            asking_price_eth=v.asking_price_eth,
            patch_status=v.patch_status,
            exclusivity=v.exclusivity,
            serious_customers_only=v.serious_customers_only,
            status=v.status,
            created_at=v.created_at,
        )
        for v in vulns
    ]


@router.get("/listings", response_model=list[ZKVulnListingResponse])
async def list_zk_vuln_listings(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Browse all active vulnerabilities for marketplace (anonymized -- no seller_pubkey).

    SC-only listings are hidden from non-Serious-Customer buyers.
    """
    # Check caller's SC status
    id_result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
    )
    identity = id_result.scalar_one_or_none()
    is_sc = identity.is_serious_customer if identity else False

    query = select(ZKVulnerability).where(ZKVulnerability.status == "active")
    if not is_sc:
        query = query.where(ZKVulnerability.serious_customers_only == False)  # noqa: E712

    result = await db.execute(query)
    vulns = result.scalars().all()
    return [
        ZKVulnListingResponse(
            id=str(v.id),
            target_software=v.target_software,
            target_version=v.target_version,
            vulnerability_class=v.vulnerability_class,
            impact_type=v.impact_type,
            cvss_self_assessed=v.cvss_self_assessed,
            asking_price_eth=v.asking_price_eth,
            patch_status=v.patch_status,
            exclusivity=v.exclusivity,
            serious_customers_only=v.serious_customers_only,
            status=v.status,
            anonymized_summary=v.anonymized_summary,
            created_at=v.created_at,
        )
        for v in vulns
    ]


# ── Agreements ──


@router.post("/agreements", response_model=ZKVulnAgreementResponse, status_code=201)
async def create_zk_agreement(
    request: ZKVulnAgreementCreateRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Propose a deal on a listed vulnerability."""
    result = await db.execute(
        select(ZKVulnerability).where(
            ZKVulnerability.id == uuid.UUID(request.vulnerability_id)
        )
    )
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    if vuln.status != "active":
        raise HTTPException(status_code=400, detail="Vulnerability is not active")
    if vuln.seller_pubkey == pubkey:
        raise HTTPException(status_code=400, detail="Cannot buy your own vulnerability")

    # SC gate: reject non-SC buyers on SC-only listings
    if vuln.serious_customers_only:
        id_result = await db.execute(
            select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
        )
        buyer_identity = id_result.scalar_one_or_none()
        if not buyer_identity or not buyer_identity.is_serious_customer:
            raise HTTPException(status_code=403, detail="This listing is restricted to Serious Customers")

    # Prevent duplicate agreements from same buyer on same vuln
    existing = await db.execute(
        select(ZKVulnAgreement).where(
            ZKVulnAgreement.vulnerability_id == vuln.id,
            ZKVulnAgreement.buyer_pubkey == pubkey,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agreement already exists for this listing")

    agreement = ZKVulnAgreement(
        vulnerability_id=vuln.id,
        seller_pubkey=vuln.seller_pubkey,
        buyer_pubkey=pubkey,
    )
    db.add(agreement)
    await db.commit()
    await db.refresh(agreement)
    return ZKVulnAgreementResponse(
        id=str(agreement.id),
        vulnerability_id=str(agreement.vulnerability_id),
        seller_pubkey=agreement.seller_pubkey,
        buyer_pubkey=agreement.buyer_pubkey,
        status=agreement.status,
        escrow_address=agreement.escrow_address,
        seller_eth_address=agreement.seller_eth_address,
        buyer_eth_address=agreement.buyer_eth_address,
        created_at=agreement.created_at,
    )


@router.get("/agreements", response_model=list[ZKVulnAgreementResponse])
async def list_zk_agreements(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List agreements where the caller is buyer or seller."""
    result = await db.execute(
        select(ZKVulnAgreement).where(
            or_(
                ZKVulnAgreement.seller_pubkey == pubkey,
                ZKVulnAgreement.buyer_pubkey == pubkey,
            )
        )
    )
    agreements = result.scalars().all()
    return [
        ZKVulnAgreementResponse(
            id=str(a.id),
            vulnerability_id=str(a.vulnerability_id),
            seller_pubkey=a.seller_pubkey,
            buyer_pubkey=a.buyer_pubkey,
            status=a.status,
            escrow_address=a.escrow_address,
            seller_eth_address=a.seller_eth_address,
            buyer_eth_address=a.buyer_eth_address,
            created_at=a.created_at,
        )
        for a in agreements
    ]


@router.get("/agreements/{agreement_id}", response_model=ZKVulnAgreementResponse)
async def get_zk_agreement(
    agreement_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Get agreement detail (must be buyer or seller)."""
    result = await db.execute(
        select(ZKVulnAgreement).where(ZKVulnAgreement.id == uuid.UUID(agreement_id))
    )
    agreement = result.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if pubkey not in (agreement.seller_pubkey, agreement.buyer_pubkey):
        raise HTTPException(status_code=403, detail="Not authorized")
    return ZKVulnAgreementResponse(
        id=str(agreement.id),
        vulnerability_id=str(agreement.vulnerability_id),
        seller_pubkey=agreement.seller_pubkey,
        buyer_pubkey=agreement.buyer_pubkey,
        status=agreement.status,
        escrow_address=agreement.escrow_address,
        seller_eth_address=agreement.seller_eth_address,
        buyer_eth_address=agreement.buyer_eth_address,
        created_at=agreement.created_at,
    )


@router.post("/agreements/{agreement_id}/wallet", response_model=ZKVulnAgreementResponse)
async def connect_wallet(
    agreement_id: str,
    request: ZKWalletConnectRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Connect an ETH wallet address to an agreement (buyer or seller)."""
    result = await db.execute(
        select(ZKVulnAgreement).where(ZKVulnAgreement.id == uuid.UUID(agreement_id))
    )
    agreement = result.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if pubkey not in (agreement.seller_pubkey, agreement.buyer_pubkey):
        raise HTTPException(status_code=403, detail="Not authorized")

    if pubkey == agreement.seller_pubkey:
        agreement.seller_eth_address = request.eth_address
    else:
        agreement.buyer_eth_address = request.eth_address

    await db.commit()
    await db.refresh(agreement)
    return ZKVulnAgreementResponse(
        id=str(agreement.id),
        vulnerability_id=str(agreement.vulnerability_id),
        seller_pubkey=agreement.seller_pubkey,
        buyer_pubkey=agreement.buyer_pubkey,
        status=agreement.status,
        escrow_address=agreement.escrow_address,
        seller_eth_address=agreement.seller_eth_address,
        buyer_eth_address=agreement.buyer_eth_address,
        created_at=agreement.created_at,
    )


# ── Negotiation ──


@router.post("/negotiations/{agreement_id}/start")
async def start_zk_negotiation(
    agreement_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Start TEE negotiation for a ZK agreement (simplified -- sets status to negotiating)."""
    if agreement_id in _statuses and _statuses[agreement_id].get("status") in (
        "pending",
        "running",
        "negotiating",
    ):
        return {"status": _statuses[agreement_id]["status"]}

    result = await db.execute(
        select(ZKVulnAgreement).where(ZKVulnAgreement.id == uuid.UUID(agreement_id))
    )
    agreement = result.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if pubkey not in (agreement.seller_pubkey, agreement.buyer_pubkey):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update agreement status
    agreement.status = "negotiating"
    await db.commit()

    _statuses[agreement_id] = {"status": "negotiating"}
    await _emit_progress(agreement_id, "started", {})

    return {"status": "negotiating"}


@router.get("/negotiations/{agreement_id}/stream")
async def stream_zk_negotiation(
    agreement_id: str,
    token: str = Query(..., description="ZK JWT token for SSE auth"),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for real-time ZK negotiation progress.

    Uses query param token because EventSource doesn't support Authorization headers.
    Rejects non-ZK tokens and verifies caller is a party to the agreement.
    """
    pubkey = decode_zk_token(token)

    # Verify caller is a party to this agreement
    result = await db.execute(
        select(ZKVulnAgreement).where(ZKVulnAgreement.id == uuid.UUID(agreement_id))
    )
    agreement = result.scalar_one_or_none()
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if pubkey not in (agreement.seller_pubkey, agreement.buyer_pubkey):
        raise HTTPException(status_code=403, detail="Not authorized")

    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    if agreement_id not in _progress_queues:
        _progress_queues[agreement_id] = []
    _progress_queues[agreement_id].append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event['phase']}\ndata: {json.dumps(event['data'])}\n\n"
                    if event["phase"] == "complete":
                        break
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in _progress_queues.get(agreement_id, []):
                _progress_queues[agreement_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _emit_progress(agreement_id: str, phase: str, data: dict | None = None):
    """Emit an SSE event to all listeners for a given agreement."""
    queues = _progress_queues.get(agreement_id, [])
    event = {"phase": phase, "data": data or {}}
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass
