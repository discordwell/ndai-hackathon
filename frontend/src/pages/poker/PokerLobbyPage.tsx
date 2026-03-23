import React, { useState, useEffect, useCallback } from "react";
import { listTables, createTable } from "../../api/poker";
import type { PokerTableSummary } from "../../api/pokerTypes";

function formatBlinds(sb: number, bb: number): string {
  if (bb >= 1_000_000) return `${(sb / 1e6).toFixed(1)}M/${(bb / 1e6).toFixed(1)}M`;
  if (bb >= 1_000) return `${(sb / 1e3).toFixed(0)}K/${(bb / 1e3).toFixed(0)}K`;
  return `${sb}/${bb}`;
}

export function PokerLobbyPage() {
  const [tables, setTables] = useState<PokerTableSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listTables();
      setTables(data);
    } catch (e: any) {
      setError(e.detail || "Failed to load tables");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); const id = setInterval(refresh, 5000); return () => clearInterval(id); }, [refresh]);

  useEffect(() => {
    if (error) { const t = setTimeout(() => setError(null), 4000); return () => clearTimeout(t); }
  }, [error]);

  const handleCreate = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const bb = parseInt(fd.get("big_blind") as string) || 200;
    try {
      await createTable({
        small_blind: Math.floor(bb / 2),
        big_blind: bb,
        min_buy_in: bb * 20,
        max_buy_in: bb * 100,
        max_seats: parseInt(fd.get("max_seats") as string) || 6,
      });
      setShowCreate(false);
      refresh();
    } catch (e: any) {
      setError(e.detail || "Failed to create table");
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Poker Tables</h1>
          <p className="text-sm text-gray-500 mt-0.5">Provably fair Texas Hold'em via Trusted Execution Environment</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const openTable = tables.find(t => t.player_count < t.max_seats);
              if (openTable) {
                window.location.hash = `#/poker/table/${openTable.id}`;
              } else {
                setError("No open tables available");
              }
            }}
            className="bg-white border border-gray-200 hover:border-ndai-300 hover:shadow-sm text-gray-700 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95"
          >
            Quick Join
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="bg-ndai-600 hover:bg-ndai-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-lg shadow-ndai-600/20 transition-all active:scale-95"
          >
            + New Table
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 px-4 py-3 rounded-xl mb-4 text-sm border border-red-200">
          {error}
        </div>
      )}

      {/* Create table form */}
      {showCreate && (
        <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Create New Table</h3>
          <form onSubmit={handleCreate} className="flex gap-4 items-end flex-wrap">
            <div>
              <label className="block text-xs text-gray-500 mb-1.5 font-medium">Big Blind</label>
              <input name="big_blind" type="number" defaultValue="200"
                className="px-3 py-2 border border-gray-200 rounded-xl text-sm w-32 focus:ring-2 focus:ring-ndai-500/20 focus:border-ndai-400 outline-none transition-all" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1.5 font-medium">Seats</label>
              <input name="max_seats" type="number" defaultValue="6" min="2" max="9"
                className="px-3 py-2 border border-gray-200 rounded-xl text-sm w-20 focus:ring-2 focus:ring-ndai-500/20 focus:border-ndai-400 outline-none transition-all" />
            </div>
            <button type="submit"
              className="bg-ndai-600 hover:bg-ndai-700 text-white px-5 py-2 rounded-xl text-sm font-medium transition-all active:scale-95">
              Create
            </button>
            <button type="button" onClick={() => setShowCreate(false)}
              className="px-4 py-2 text-gray-500 hover:text-gray-700 text-sm transition-colors">
              Cancel
            </button>
          </form>
        </div>
      )}

      {/* Table list */}
      {loading ? (
        <div className="text-center py-16">
          <div className="w-8 h-8 mx-auto rounded-full border-2 border-ndai-500/30 border-t-ndai-500 animate-spin mb-3" />
          <span className="text-gray-400 text-sm">Loading tables...</span>
        </div>
      ) : tables.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gray-100 flex items-center justify-center">
            <span className="text-2xl">&#x1F0CF;</span>
          </div>
          <p className="text-gray-500 mb-1">No tables available</p>
          <p className="text-gray-400 text-sm">Create one to get started</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {tables.map(t => (
            <a
              key={t.id}
              href={`#/poker/table/${t.id}`}
              className="group block bg-white border border-gray-200 rounded-2xl p-5 hover:border-ndai-300 hover:shadow-md transition-all"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Table icon */}
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-felt-500 to-felt-700 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow">
                    <span className="text-white text-sm font-bold">
                      {formatBlinds(t.small_blind, t.big_blind)}
                    </span>
                  </div>
                  <div>
                    <span className="font-semibold text-gray-900 group-hover:text-ndai-700 transition-colors">
                      Table {t.id.slice(0, 8)}
                    </span>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-400">
                        Buy-in: {t.min_buy_in.toLocaleString()}&ndash;{t.max_buy_in.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {/* Player count */}
                  <div className="text-right">
                    <div className="flex items-center gap-1.5">
                      {Array.from({ length: t.max_seats }, (_, i) => (
                        <div
                          key={i}
                          className={`w-2 h-2 rounded-full ${
                            i < t.player_count ? "bg-emerald-400" : "bg-gray-200"
                          }`}
                        />
                      ))}
                    </div>
                    <span className="text-xs text-gray-400 mt-1 block">
                      {t.player_count}/{t.max_seats} seated
                    </span>
                  </div>

                  {/* Seated badge */}
                  {t.my_seat != null && (
                    <span className="text-xs px-3 py-1 rounded-full font-medium bg-ndai-50 text-ndai-700 border border-ndai-200 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-ndai-500" />
                      Seated
                    </span>
                  )}

                  {/* Status */}
                  <span className={`text-xs px-3 py-1 rounded-full font-medium ${
                    t.player_count > 0
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-gray-50 text-gray-500 border border-gray-200"
                  }`}>
                    {t.player_count > 0 ? "Playing" : "Open"}
                  </span>

                  {/* Arrow */}
                  <span className="text-gray-300 group-hover:text-ndai-500 group-hover:translate-x-0.5 transition-all">
                    &#x2192;
                  </span>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
