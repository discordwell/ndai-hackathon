import React, { useState, useEffect } from "react";
import {
  getAuction,
  listBids,
  endAuction,
  settleAuction,
  cancelAuction,
  type ZKAuctionResponse,
  type ZKAuctionBidResponse,
} from "../../api/zkAuctions";
import { useZKAuth } from "../../contexts/ZKAuthContext";

function timeRemaining(endTime: string | null): string {
  if (!endTime) return "N/A";
  const diff = new Date(endTime).getTime() - Date.now();
  if (diff <= 0) return "Ended";
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  const secs = Math.floor((diff % 60000) / 1000);
  if (hours > 0) return `${hours}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

export function ZKAuctionPage({ auctionId }: { auctionId: string }) {
  const { publicKeyHex } = useZKAuth();
  const [auction, setAuction] = useState<ZKAuctionResponse | null>(null);
  const [bids, setBids] = useState<ZKAuctionBidResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [acting, setActing] = useState(false);
  const [countdown, setCountdown] = useState("");

  useEffect(() => {
    Promise.all([getAuction(auctionId), listBids(auctionId)])
      .then(([a, b]) => {
        setAuction(a);
        setBids(b);
      })
      .catch((e) => setError(e.message || "Failed to load auction"))
      .finally(() => setLoading(false));
  }, [auctionId]);

  // Countdown timer
  useEffect(() => {
    if (!auction?.end_time) return;
    const interval = setInterval(() => {
      setCountdown(timeRemaining(auction.end_time));
    }, 1000);
    setCountdown(timeRemaining(auction.end_time));
    return () => clearInterval(interval);
  }, [auction?.end_time]);

  const isSeller = auction?.seller_pubkey === publicKeyHex;
  const isEnded = countdown === "Ended" || auction?.status === "ended";

  async function handleAction(action: "end" | "settle" | "cancel") {
    setActing(true);
    setActionError("");
    try {
      let updated: ZKAuctionResponse;
      if (action === "end") updated = await endAuction(auctionId);
      else if (action === "settle") updated = await settleAuction(auctionId);
      else updated = await cancelAuction(auctionId);
      setAuction(updated);
    } catch (err: any) {
      setActionError(err.message || `Failed to ${action}`);
    } finally {
      setActing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-void-400" />
      </div>
    );
  }
  if (error || !auction) {
    return <div className="text-red-400 text-sm">{error || "Auction not found"}</div>;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-void-50">Auction</h1>
        <span
          className={`text-xs px-2 py-1 rounded font-medium ${
            auction.status === "active"
              ? "bg-green-500/20 text-green-400"
              : auction.status === "ended"
              ? "bg-yellow-500/20 text-yellow-400"
              : auction.status === "settled"
              ? "bg-blue-500/20 text-blue-400"
              : "bg-void-700 text-void-400"
          }`}
        >
          {auction.status}
        </span>
      </div>

      {/* Auction Info */}
      <div className="bg-void-800 border border-void-700 rounded-lg p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="text-void-400 block mb-1">Reserve Price</span>
            <span className="text-void-50 font-medium">{auction.reserve_price_eth} ETH</span>
          </div>
          <div>
            <span className="text-void-400 block mb-1">Highest Bid</span>
            <span className="text-void-50 font-medium">
              {auction.highest_bid_eth ? `${auction.highest_bid_eth} ETH` : "No bids"}
            </span>
          </div>
          <div>
            <span className="text-void-400 block mb-1">Time Remaining</span>
            <span className={`font-medium font-mono ${isEnded ? "text-red-400" : "text-green-400"}`}>
              {countdown}
            </span>
          </div>
          <div>
            <span className="text-void-400 block mb-1">Access</span>
            {auction.serious_customers_only ? (
              <span className="text-amber-400 font-medium">SC Only</span>
            ) : (
              <span className="text-void-200 font-medium">Open</span>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      {actionError && (
        <div className="text-xs text-red-400 bg-red-900/30 border border-red-800 rounded px-3 py-2">
          {actionError}
        </div>
      )}

      <div className="flex gap-2">
        {auction.status === "active" && isEnded && (
          <button
            onClick={() => handleAction("end")}
            disabled={acting}
            className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded text-xs font-medium disabled:opacity-50 transition-colors"
          >
            End Auction
          </button>
        )}
        {auction.status === "ended" && isSeller && auction.highest_bid_eth && (
          <button
            onClick={() => handleAction("settle")}
            disabled={acting}
            className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded text-xs font-medium disabled:opacity-50 transition-colors"
          >
            Settle (Accept Highest Bid)
          </button>
        )}
        {auction.status === "active" && isSeller && !auction.highest_bid_eth && (
          <button
            onClick={() => handleAction("cancel")}
            disabled={acting}
            className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded text-xs font-medium disabled:opacity-50 transition-colors"
          >
            Cancel Auction
          </button>
        )}
      </div>

      {/* Bid History */}
      <div className="bg-void-800 border border-void-700 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-void-50 mb-3">Bid History</h2>
        {bids.length === 0 ? (
          <p className="text-xs text-void-400">No bids yet</p>
        ) : (
          <div className="space-y-2">
            {bids.map((b) => (
              <div
                key={b.id}
                className={`flex items-center justify-between p-3 rounded border text-xs ${
                  b.is_highest
                    ? "border-green-500/30 bg-green-900/10"
                    : "border-void-700 bg-void-900"
                }`}
              >
                <div>
                  <span className="text-void-200 font-mono">
                    {b.bidder_pubkey.slice(0, 12)}...
                  </span>
                  {b.is_highest && (
                    <span className="ml-2 text-green-400 font-medium">Highest</span>
                  )}
                </div>
                <div className="text-void-50 font-medium">{b.bid_eth} ETH</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
