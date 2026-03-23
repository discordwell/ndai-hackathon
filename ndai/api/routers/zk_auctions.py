"""ZK-authenticated auction endpoints for the zero-day marketplace."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.api.dependencies import get_zk_identity
from ndai.api.schemas.zk_auction import (
    ZKAuctionBidRequest,
    ZKAuctionBidResponse,
    ZKAuctionCreateRequest,
    ZKAuctionResponse,
)
from ndai.db.session import get_db
from ndai.models.zk_auction import ZKVulnAuction, ZKVulnAuctionBid
from ndai.models.zk_identity import VulnIdentity
from ndai.models.zk_vulnerability import ZKVulnerability

router = APIRouter(prefix="", tags=["zk-auctions"])
logger = logging.getLogger(__name__)


def _auction_response(a: ZKVulnAuction) -> ZKAuctionResponse:
    return ZKAuctionResponse(
        id=str(a.id),
        vulnerability_id=str(a.vulnerability_id),
        seller_pubkey=a.seller_pubkey,
        reserve_price_eth=a.reserve_price_eth,
        duration_hours=a.duration_hours,
        serious_customers_only=a.serious_customers_only,
        status=a.status,
        highest_bid_eth=a.highest_bid_eth,
        highest_bidder_pubkey=a.highest_bidder_pubkey,
        end_time=a.end_time,
        auction_contract_address=a.auction_contract_address,
        created_at=a.created_at,
    )


# ── Create ──


@router.post("/", response_model=ZKAuctionResponse, status_code=201)
async def create_auction(
    request: ZKAuctionCreateRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Create an auction for an owned vulnerability listing."""
    result = await db.execute(
        select(ZKVulnerability).where(
            ZKVulnerability.id == uuid.UUID(request.vulnerability_id)
        )
    )
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    if vuln.seller_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Not the owner")
    if vuln.status != "active":
        raise HTTPException(status_code=400, detail="Vulnerability not active")

    # Prevent duplicate active auctions for the same vulnerability
    existing = await db.execute(
        select(ZKVulnAuction).where(
            ZKVulnAuction.vulnerability_id == vuln.id,
            ZKVulnAuction.status.in_(["active", "ended"]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Active auction already exists for this vulnerability")

    end_time = datetime.now(timezone.utc) + timedelta(hours=request.duration_hours)

    auction = ZKVulnAuction(
        vulnerability_id=vuln.id,
        seller_pubkey=pubkey,
        reserve_price_eth=request.reserve_price_eth,
        duration_hours=request.duration_hours,
        serious_customers_only=request.serious_customers_only,
        status="active",
        end_time=end_time,
    )
    db.add(auction)
    await db.commit()
    await db.refresh(auction)
    return _auction_response(auction)


# ── List ──


@router.get("/", response_model=list[ZKAuctionResponse])
async def list_auctions(
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List active auctions. SC-only auctions are hidden from non-SC users."""
    # Check SC status
    id_result = await db.execute(
        select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
    )
    identity = id_result.scalar_one_or_none()
    is_sc = identity.is_serious_customer if identity else False

    query = select(ZKVulnAuction).where(ZKVulnAuction.status.in_(["active", "ended"]))
    if not is_sc:
        query = query.where(ZKVulnAuction.serious_customers_only == False)  # noqa: E712

    result = await db.execute(query)
    auctions = result.scalars().all()
    return [_auction_response(a) for a in auctions]


# ── Detail ──


@router.get("/{auction_id}", response_model=ZKAuctionResponse)
async def get_auction(
    auction_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Get auction detail."""
    result = await db.execute(
        select(ZKVulnAuction).where(ZKVulnAuction.id == uuid.UUID(auction_id))
    )
    auction = result.scalar_one_or_none()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    # SC-only gate
    if auction.serious_customers_only:
        id_result = await db.execute(
            select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
        )
        identity = id_result.scalar_one_or_none()
        if not identity or not identity.is_serious_customer:
            raise HTTPException(status_code=403, detail="Serious Customers only")

    return _auction_response(auction)


# ── Bid ──


@router.post("/{auction_id}/bid", response_model=ZKAuctionBidResponse, status_code=201)
async def place_bid(
    auction_id: str,
    request: ZKAuctionBidRequest,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Place a bid on an auction."""
    result = await db.execute(
        select(ZKVulnAuction).where(ZKVulnAuction.id == uuid.UUID(auction_id))
    )
    auction = result.scalar_one_or_none()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.status != "active":
        raise HTTPException(status_code=400, detail="Auction not active")
    if auction.seller_pubkey == pubkey:
        raise HTTPException(status_code=400, detail="Cannot bid on your own auction")

    # Time check
    if auction.end_time and datetime.now(timezone.utc) >= auction.end_time:
        raise HTTPException(status_code=400, detail="Auction has ended")

    # SC gate
    if auction.serious_customers_only:
        id_result = await db.execute(
            select(VulnIdentity).where(VulnIdentity.public_key == pubkey)
        )
        identity = id_result.scalar_one_or_none()
        if not identity or not identity.is_serious_customer:
            raise HTTPException(status_code=403, detail="Serious Customers only")

    # Bid must exceed current highest
    if auction.highest_bid_eth and request.bid_eth <= auction.highest_bid_eth:
        raise HTTPException(status_code=400, detail="Bid must exceed current highest")
    if request.bid_eth < auction.reserve_price_eth:
        raise HTTPException(status_code=400, detail="Bid below reserve price")

    # Mark previous highest bid as not highest
    if auction.highest_bidder_pubkey:
        prev_bids = await db.execute(
            select(ZKVulnAuctionBid).where(
                ZKVulnAuctionBid.auction_id == auction.id,
                ZKVulnAuctionBid.is_highest == True,  # noqa: E712
            )
        )
        for prev in prev_bids.scalars().all():
            prev.is_highest = False

    # Create bid record
    bid = ZKVulnAuctionBid(
        auction_id=auction.id,
        bidder_pubkey=pubkey,
        bidder_eth_address=request.eth_address,
        bid_eth=request.bid_eth,
        bid_tx_hash=request.bid_tx_hash,
        is_highest=True,
    )
    db.add(bid)

    # Update auction
    auction.highest_bid_eth = request.bid_eth
    auction.highest_bidder_pubkey = pubkey
    auction.highest_bidder_eth_address = request.eth_address

    await db.commit()
    await db.refresh(bid)

    return ZKAuctionBidResponse(
        id=str(bid.id),
        auction_id=str(bid.auction_id),
        bidder_pubkey=bid.bidder_pubkey,
        bid_eth=bid.bid_eth,
        bid_tx_hash=bid.bid_tx_hash,
        is_highest=bid.is_highest,
        created_at=bid.created_at,
    )


# ── Lifecycle ──


@router.post("/{auction_id}/end", response_model=ZKAuctionResponse)
async def end_auction(
    auction_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """End an auction after its duration has elapsed."""
    result = await db.execute(
        select(ZKVulnAuction).where(ZKVulnAuction.id == uuid.UUID(auction_id))
    )
    auction = result.scalar_one_or_none()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.status != "active":
        raise HTTPException(status_code=400, detail="Auction not active")
    if auction.end_time and datetime.now(timezone.utc) < auction.end_time:
        raise HTTPException(status_code=400, detail="Auction has not ended yet")

    auction.status = "ended"
    await db.commit()
    await db.refresh(auction)
    return _auction_response(auction)


@router.post("/{auction_id}/settle", response_model=ZKAuctionResponse)
async def settle_auction(
    auction_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Seller settles the auction (confirms the deal)."""
    result = await db.execute(
        select(ZKVulnAuction).where(ZKVulnAuction.id == uuid.UUID(auction_id))
    )
    auction = result.scalar_one_or_none()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.seller_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Only seller can settle")
    if auction.status != "ended":
        raise HTTPException(status_code=400, detail="Auction not in ended state")
    if not auction.highest_bidder_pubkey:
        raise HTTPException(status_code=400, detail="No bids to settle")

    auction.status = "settled"
    await db.commit()
    await db.refresh(auction)
    return _auction_response(auction)


@router.post("/{auction_id}/cancel", response_model=ZKAuctionResponse)
async def cancel_auction(
    auction_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """Seller cancels the auction (only if no bids)."""
    result = await db.execute(
        select(ZKVulnAuction).where(ZKVulnAuction.id == uuid.UUID(auction_id))
    )
    auction = result.scalar_one_or_none()
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.seller_pubkey != pubkey:
        raise HTTPException(status_code=403, detail="Only seller can cancel")
    if auction.status != "active":
        raise HTTPException(status_code=400, detail="Auction not active")
    if auction.highest_bidder_pubkey:
        raise HTTPException(status_code=400, detail="Cannot cancel: has bids")

    auction.status = "cancelled"
    await db.commit()
    await db.refresh(auction)
    return _auction_response(auction)


# ── Bids ──


@router.get("/{auction_id}/bids", response_model=list[ZKAuctionBidResponse])
async def list_bids(
    auction_id: str,
    pubkey: str = Depends(get_zk_identity),
    db: AsyncSession = Depends(get_db),
):
    """List all bids for an auction."""
    result = await db.execute(
        select(ZKVulnAuctionBid)
        .where(ZKVulnAuctionBid.auction_id == uuid.UUID(auction_id))
        .order_by(ZKVulnAuctionBid.bid_eth.desc())
    )
    bids = result.scalars().all()
    return [
        ZKAuctionBidResponse(
            id=str(b.id),
            auction_id=str(b.auction_id),
            bidder_pubkey=b.bidder_pubkey,
            bid_eth=b.bid_eth,
            bid_tx_hash=b.bid_tx_hash,
            is_highest=b.is_highest,
            created_at=b.created_at,
        )
        for b in bids
    ]
