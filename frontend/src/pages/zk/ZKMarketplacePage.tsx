import React, { useState, useEffect } from "react";
import {
  listVulnListings,
  createAgreement,
  type ZKVulnListingResponse,
} from "../../api/zkVulns";
import {
  listOpenBounties,
  type BountyResponse,
} from "../../api/bounties";
import {
  listAuctions,
  type ZKAuctionResponse,
} from "../../api/zkAuctions";

const IMPACT_COLORS: Record<string, string> = {
  RCE: "bg-red-500/20 text-red-400 border-red-500/30",
  LPE: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  InfoLeak: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  DoS: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

function cvssColor(score: number): string {
  if (score >= 9) return "text-red-400";
  if (score >= 7) return "text-orange-400";
  if (score >= 4) return "text-yellow-400";
  return "text-green-400";
}

export function ZKMarketplacePage() {
  const [tab, setTab] = useState<"listings" | "bounties" | "auctions">("listings");
  const [listings, setListings] = useState<ZKVulnListingResponse[]>([]);
  const [bounties, setBounties] = useState<BountyResponse[]>([]);
  const [auctions, setAuctions] = useState<ZKAuctionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Deal proposal state
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    if (tab === "listings") {
      listVulnListings()
        .then(setListings)
        .catch((e) => setError(e.message || "Failed to load listings"))
        .finally(() => setLoading(false));
    } else if (tab === "bounties") {
      listOpenBounties()
        .then(setBounties)
        .catch((e) => setError(e.message || "Failed to load bounties"))
        .finally(() => setLoading(false));
    } else {
      listAuctions()
        .then(setAuctions)
        .catch((e) => setError(e.message || "Failed to load auctions"))
        .finally(() => setLoading(false));
    }
  }, [tab]);

  async function handleProposeDeal() {
    if (!selectedId) return;
    setCreating(true);
    setCreateError("");
    try {
      const agreement = await createAgreement({ vulnerability_id: selectedId });
      window.location.hash = `#/zk/deals/${agreement.id}`;
    } catch (err: any) {
      setCreateError(err.message || "Failed to create agreement");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-void-50">Marketplace</h1>
        <div className="flex gap-2">
          <a
            href="#/zk/submit"
            className="px-3 py-1.5 bg-void-500 hover:bg-void-400 text-white rounded text-xs font-medium transition-colors"
          >
            + Submit Vuln
          </a>
          {tab === "bounties" && (
            <a
              href="#/zk/bounty/new"
              className="px-3 py-1.5 bg-void-500 hover:bg-void-400 text-white rounded text-xs font-medium transition-colors"
            >
              + Post Bounty
            </a>
          )}
          {tab === "auctions" && (
            <a
              href="#/zk/auctions/new"
              className="px-3 py-1.5 bg-void-500 hover:bg-void-400 text-white rounded text-xs font-medium transition-colors"
            >
              + Create Auction
            </a>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-void-700">
        <button
          onClick={() => setTab("listings")}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
            tab === "listings"
              ? "border-void-400 text-void-50"
              : "border-transparent text-void-400 hover:text-void-200"
          }`}
        >
          Listings
        </button>
        <button
          onClick={() => setTab("bounties")}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
            tab === "bounties"
              ? "border-void-400 text-void-50"
              : "border-transparent text-void-400 hover:text-void-200"
          }`}
        >
          Bounties
        </button>
        <button
          onClick={() => setTab("auctions")}
          className={`px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
            tab === "auctions"
              ? "border-void-400 text-void-50"
              : "border-transparent text-void-400 hover:text-void-200"
          }`}
        >
          Auctions
        </button>
      </div>

      {/* Loading / Error */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-void-400" />
        </div>
      ) : error ? (
        <div className="text-red-400 text-sm">{error}</div>
      ) : tab === "listings" ? (
        /* ── Listings Tab ── */
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {listings.length === 0 ? (
              <div className="col-span-full text-center py-12 text-void-400 text-sm">
                No listings available
              </div>
            ) : (
              listings.map((v) => (
                <div
                  key={v.id}
                  onClick={() => setSelectedId(v.id)}
                  className={`bg-void-800 border rounded-lg p-4 cursor-pointer transition-all ${
                    selectedId === v.id
                      ? "border-void-400 ring-1 ring-void-500"
                      : "border-void-700 hover:border-void-500"
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-sm font-semibold text-void-50 truncate pr-2">
                      {v.target_software}
                    </h3>
                    <span
                      className={`text-[10px] font-medium px-1.5 py-0.5 rounded border shrink-0 ${
                        IMPACT_COLORS[v.impact_type] ||
                        "bg-void-700 text-void-300 border-void-600"
                      }`}
                    >
                      {v.impact_type}
                    </span>
                  </div>

                  <p className="text-xs text-void-400 mb-2">
                    {v.vulnerability_class}
                  </p>

                  <div className="flex items-center gap-3 text-xs mb-2">
                    <span className={`font-mono font-bold ${cvssColor(v.cvss_self_assessed)}`}>
                      {v.cvss_self_assessed.toFixed(1)}
                    </span>
                    <span className="text-void-200 font-medium">
                      {v.asking_price_eth} ETH
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded ${
                        v.exclusivity === "exclusive"
                          ? "bg-purple-500/20 text-purple-400"
                          : "bg-void-700 text-void-400"
                      }`}
                    >
                      {v.exclusivity}
                    </span>
                    {v.serious_customers_only && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                        SC Only
                      </span>
                    )}
                  </div>

                  {v.anonymized_summary && (
                    <p className="text-xs text-void-400 line-clamp-2 leading-relaxed">
                      {v.anonymized_summary}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Propose Deal panel */}
          {selectedId && (
            <div className="bg-void-800 border border-void-700 rounded-lg p-4 h-fit sticky top-4">
              <h3 className="text-sm font-semibold text-void-50 mb-3">
                Propose Deal
              </h3>
              <p className="text-xs text-void-400 font-mono mb-4">
                {selectedId.slice(0, 16)}...
              </p>

              {createError && (
                <div className="text-xs text-red-400 bg-red-900/30 border border-red-800 rounded px-2 py-1.5 mb-3">
                  {createError}
                </div>
              )}

              <button
                onClick={handleProposeDeal}
                disabled={creating}
                className="w-full py-2 bg-void-500 hover:bg-void-400 text-white rounded text-sm font-medium disabled:opacity-50 transition-colors"
              >
                {creating ? "Creating..." : "Confirm & Propose"}
              </button>

              <button
                onClick={() => setSelectedId(null)}
                className="w-full py-1.5 text-void-400 hover:text-void-200 text-xs mt-2 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      ) : tab === "bounties" ? (
        /* ── Bounties Tab ── */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {bounties.length === 0 ? (
            <div className="col-span-full text-center py-12 text-void-400 text-sm">
              No open bounties
            </div>
          ) : (
            bounties.map((b) => (
              <div
                key={b.id}
                className="bg-void-800 border border-void-700 hover:border-void-500 rounded-lg p-4 transition-all"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-sm font-semibold text-void-50 truncate pr-2">
                    {b.target_software}
                  </h3>
                  <span
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded border shrink-0 ${
                      IMPACT_COLORS[b.desired_impact] ||
                      "bg-void-700 text-void-300 border-void-600"
                    }`}
                  >
                    {b.desired_impact}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-xs mb-2">
                  <span className="text-void-200 font-medium">
                    {b.budget_eth} ETH budget
                  </span>
                  {b.deadline && (
                    <span className="text-void-400">
                      Due: {new Date(b.deadline).toLocaleDateString()}
                    </span>
                  )}
                </div>

                <p className="text-xs text-void-400 line-clamp-2 mb-3 leading-relaxed">
                  {b.description}
                </p>

                <a
                  href={`#/zk/bounty/${b.id}/respond`}
                  className="inline-block px-3 py-1.5 bg-void-600 hover:bg-void-500 text-void-50 rounded text-xs font-medium transition-colors"
                >
                  Respond
                </a>
              </div>
            ))
          )}
        </div>
      ) : (
        /* ── Auctions Tab ── */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {auctions.length === 0 ? (
            <div className="col-span-full text-center py-12 text-void-400 text-sm">
              No active auctions
            </div>
          ) : (
            auctions.map((a) => {
              const endDate = a.end_time ? new Date(a.end_time) : null;
              const isEnded = endDate ? endDate.getTime() <= Date.now() : false;
              return (
                <a
                  key={a.id}
                  href={`#/zk/auctions/${a.id}`}
                  className="bg-void-800 border border-void-700 hover:border-void-500 rounded-lg p-4 transition-all block"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-sm font-semibold text-void-50 truncate pr-2">
                      Auction
                    </h3>
                    <div className="flex gap-1">
                      {a.serious_customers_only && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 shrink-0">
                          SC Only
                        </span>
                      )}
                      <span
                        className={`text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 ${
                          isEnded || a.status === "ended"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : a.status === "settled"
                            ? "bg-blue-500/20 text-blue-400"
                            : "bg-green-500/20 text-green-400"
                        }`}
                      >
                        {a.status}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-xs mb-2">
                    <span className="text-void-400">Reserve:</span>
                    <span className="text-void-200 font-medium">
                      {a.reserve_price_eth} ETH
                    </span>
                    <span className="text-void-400">Highest:</span>
                    <span className="text-void-50 font-medium">
                      {a.highest_bid_eth ? `${a.highest_bid_eth} ETH` : "—"}
                    </span>
                  </div>

                  {endDate && (
                    <p className="text-xs text-void-400">
                      {isEnded
                        ? `Ended ${endDate.toLocaleDateString()}`
                        : `Ends ${endDate.toLocaleDateString()} ${endDate.toLocaleTimeString()}`}
                    </p>
                  )}
                </a>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
