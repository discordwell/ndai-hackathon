import React, { useState, useEffect, useCallback } from "react";
import { listTables, listHands, getHandDetail } from "../../api/poker";
import type { PokerTableSummary, HandSummary, HandDetail } from "../../api/pokerTypes";
import PlayingCard from "../../components/poker/PlayingCard";
import { VerificationPanel } from "../../components/shared/VerificationPanel";

function formatBlinds(sb: number, bb: number): string {
  if (bb >= 1_000_000) return `${(sb / 1e6).toFixed(1)}M/${(bb / 1e6).toFixed(1)}M`;
  if (bb >= 1_000) return `${(sb / 1e3).toFixed(0)}K/${(bb / 1e3).toFixed(0)}K`;
  return `${sb}/${bb}`;
}

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function formatChips(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 10_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

const ACTION_COLORS: Record<string, string> = {
  fold: "text-red-500",
  check: "text-gray-400",
  call: "text-blue-400",
  bet: "text-gold-400",
  raise: "text-gold-400",
  all_in: "text-emerald-400",
  timeout_fold: "text-red-400",
};

function ActionLabel({ action, amount }: { action: string; amount: number }) {
  const color = ACTION_COLORS[action] || "text-gray-400";
  const label = action === "timeout_fold" ? "Timed out" :
    action === "all_in" ? "All In" :
    action.charAt(0).toUpperCase() + action.slice(1);
  return (
    <span className={`${color} font-medium`}>
      {label}{amount > 0 && action !== "fold" && action !== "check" ? ` ${formatChips(amount)}` : ""}
    </span>
  );
}

function HandCard({
  hand,
  onExpand,
  isExpanded,
  detail,
}: {
  hand: HandSummary;
  onExpand: () => void;
  isExpanded: boolean;
  detail: HandDetail | null;
}) {
  const totalPot = hand.pots_awarded?.reduce((s, p) => s + (p.amount || 0), 0) ?? 0;
  const winner = hand.pots_awarded?.[0];
  const hasVerification = detail?.verification != null;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden transition-all hover:border-ndai-300 hover:shadow-sm">
      {/* Summary row */}
      <button
        onClick={onExpand}
        className="w-full text-left p-5 flex items-center gap-4"
      >
        {/* Hand number badge */}
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-felt-500 to-felt-700 flex items-center justify-center shadow-sm shrink-0">
          <span className="text-white text-xs font-bold">#{hand.hand_number}</span>
        </div>

        {/* Info column */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900 text-sm">
              Hand #{hand.hand_number}
            </span>
            {hand.small_blind != null && hand.big_blind != null && (
              <span className="text-xs text-gray-400">
                {formatBlinds(hand.small_blind, hand.big_blind)} blinds
              </span>
            )}
            {hand.ended_at && (
              <span className="text-xs text-gray-400 ml-auto shrink-0">
                {timeAgo(hand.ended_at)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1.5">
            {/* Community cards */}
            <div className="flex gap-1">
              {hand.community_cards && hand.community_cards.length > 0 ? (
                hand.community_cards.map((c, i) => (
                  <PlayingCard key={i} card={c} size="sm" />
                ))
              ) : (
                Array.from({ length: 5 }, (_, i) => (
                  <div
                    key={i}
                    className="rounded border border-gray-200 bg-gray-50"
                    style={{ width: 28, height: 40 }}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        {/* Results column */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Pot */}
          {totalPot > 0 && (
            <div className="text-right">
              <div className="text-xs text-gray-400">Pot</div>
              <div className="text-sm font-bold text-gray-900 tabular-nums">{formatChips(totalPot)}</div>
            </div>
          )}

          {/* Winner */}
          {winner && (
            <div className="text-right">
              <div className="text-xs text-gray-400">Winner</div>
              <div className="text-sm font-semibold text-emerald-600">
                {winner.hand_rank || "—"}
              </div>
            </div>
          )}

          {/* Verification + settlement badges */}
          <div className="flex gap-1.5 ml-2">
            {hand.settlement_tx_hash && (
              <a
                href={`https://sepolia.basescan.org/tx/${hand.settlement_tx_hash}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="w-7 h-7 rounded-full bg-blue-50 border border-blue-200 flex items-center justify-center hover:bg-blue-100 transition-colors"
                title="View on-chain settlement"
              >
                <span className="text-blue-500 text-xs">&#x26D3;</span>
              </a>
            )}
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center border ${
                hand.deck_seed_hash
                  ? "bg-emerald-50 border-emerald-200"
                  : "bg-gray-50 border-gray-200"
              }`}
              title={hand.deck_seed_hash ? "TEE verified" : "Pending verification"}
            >
              <span className={`text-xs ${hand.deck_seed_hash ? "text-emerald-500" : "text-gray-400"}`}>
                &#x2713;
              </span>
            </div>
          </div>

          {/* Expand arrow */}
          <span className={`text-gray-300 transition-transform ${isExpanded ? "rotate-90" : ""}`}>
            &#x2192;
          </span>
        </div>
      </button>

      {/* Expanded detail */}
      {isExpanded && detail && (
        <div className="border-t border-gray-100 bg-gray-50/50 p-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Action replay */}
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Action Replay</h4>
              {detail.actions.length > 0 ? (
                <div className="space-y-1.5">
                  {detail.actions.map((a, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="text-gray-400 text-xs w-16 shrink-0 uppercase">{a.phase}</span>
                      <span className="text-gray-600">Seat {a.seat_index}</span>
                      <ActionLabel action={a.action} amount={a.amount} />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400">No actions recorded</p>
              )}
            </div>

            {/* Pot breakdown + metadata */}
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Details</h4>
              <div className="space-y-2 text-sm">
                {detail.pots_awarded?.map((p, i) => (
                  <div key={i} className="flex justify-between">
                    <span className="text-gray-500">
                      {detail.pots_awarded!.length > 1 ? `Pot ${i + 1}` : "Pot"}
                    </span>
                    <span className="font-medium text-gray-900">
                      {formatChips(p.amount)} &rarr; {p.hand_rank || "Winner"}
                    </span>
                  </div>
                ))}
                {detail.deck_seed_hash && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <div className="text-xs text-gray-400 mb-1">Deck Seed Hash</div>
                    <code className="text-xs text-gray-600 break-all bg-white px-2 py-1 rounded border border-gray-200 block">
                      {detail.deck_seed_hash}
                    </code>
                  </div>
                )}
                {detail.result_hash && (
                  <div>
                    <div className="text-xs text-gray-400 mb-1">Result Hash</div>
                    <code className="text-xs text-gray-600 break-all bg-white px-2 py-1 rounded border border-gray-200 block">
                      {detail.result_hash}
                    </code>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Verification panel */}
          {hasVerification && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <VerificationPanel verification={detail.verification} defaultExpanded={false} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function PokerHistoryPage() {
  const [tables, setTables] = useState<PokerTableSummary[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>("");
  const [hands, setHands] = useState<HandSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedHand, setExpandedHand] = useState<string | null>(null);
  const [handDetails, setHandDetails] = useState<Record<string, HandDetail>>({});
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load tables for filter
  useEffect(() => {
    listTables().then(setTables).catch(() => {});
  }, []);

  // Load hands when table selection changes
  const loadHands = useCallback(async (tableId: string, before?: number) => {
    if (!tableId) {
      setHands([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await listHands(tableId, { limit: 20, before });
      if (before) {
        setHands(prev => [...prev, ...data]);
      } else {
        setHands(data);
      }
      setHasMore(data.length === 20);
    } catch (e: any) {
      setError(e.detail || "Failed to load hands");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedTable) {
      loadHands(selectedTable);
    } else if (tables.length > 0) {
      // Auto-select first table
      setSelectedTable(tables[0].id);
    }
  }, [selectedTable, tables, loadHands]);

  const handleExpand = async (hand: HandSummary) => {
    const key = `${hand.table_id}:${hand.hand_number}`;
    if (expandedHand === key) {
      setExpandedHand(null);
      return;
    }
    setExpandedHand(key);

    // Fetch full detail if not cached
    if (!handDetails[key]) {
      try {
        const detail = await getHandDetail(hand.table_id, hand.hand_number);
        setHandDetails(prev => ({ ...prev, [key]: detail }));
      } catch {
        // Detail fetch failed — expand anyway with what we have
      }
    }
  };

  const handleLoadMore = () => {
    if (hands.length > 0 && selectedTable) {
      const lastHand = hands[hands.length - 1];
      loadHands(selectedTable, lastHand.hand_number);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Hand History</h1>
          <p className="text-sm text-gray-500 mt-0.5">Review past hands with TEE verification and on-chain settlement</p>
        </div>

        {/* Table filter */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500 font-medium">Table</label>
          <select
            value={selectedTable}
            onChange={(e) => {
              setSelectedTable(e.target.value);
              setHands([]);
              setExpandedHand(null);
            }}
            className="px-3 py-2 border border-gray-200 rounded-xl text-sm bg-white focus:ring-2 focus:ring-ndai-500/20 focus:border-ndai-400 outline-none transition-all"
          >
            <option value="">Select a table</option>
            {tables.map(t => (
              <option key={t.id} value={t.id}>
                Table {t.id.slice(0, 8)} ({formatBlinds(t.small_blind, t.big_blind)})
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 px-4 py-3 rounded-xl mb-4 text-sm border border-red-200">
          {error}
        </div>
      )}

      {/* Hands list */}
      {!selectedTable ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gray-100 flex items-center justify-center">
            <span className="text-2xl">&#x1F0CF;</span>
          </div>
          <p className="text-gray-500 mb-1">Select a table to view hand history</p>
          <p className="text-gray-400 text-sm">Choose from the dropdown above</p>
        </div>
      ) : loading && hands.length === 0 ? (
        <div className="text-center py-16">
          <div className="w-8 h-8 mx-auto rounded-full border-2 border-ndai-500/30 border-t-ndai-500 animate-spin mb-3" />
          <span className="text-gray-400 text-sm">Loading hands...</span>
        </div>
      ) : hands.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gray-100 flex items-center justify-center">
            <span className="text-2xl">&#x1F4DC;</span>
          </div>
          <p className="text-gray-500 mb-1">No completed hands</p>
          <p className="text-gray-400 text-sm">Hands will appear here after they are played</p>
        </div>
      ) : (
        <div className="space-y-3">
          {hands.map(h => {
            const key = `${h.table_id}:${h.hand_number}`;
            return (
              <HandCard
                key={key}
                hand={h}
                onExpand={() => handleExpand(h)}
                isExpanded={expandedHand === key}
                detail={handDetails[key] || null}
              />
            );
          })}

          {/* Load more */}
          {hasMore && (
            <div className="text-center pt-4">
              <button
                onClick={handleLoadMore}
                disabled={loading}
                className="px-6 py-2.5 rounded-xl bg-white border border-gray-200 hover:border-ndai-300 hover:shadow-sm text-sm font-medium text-gray-600 transition-all disabled:opacity-50"
              >
                {loading ? "Loading..." : "Load more"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
