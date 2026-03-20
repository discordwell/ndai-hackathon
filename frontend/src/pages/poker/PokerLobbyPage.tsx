import React, { useState, useEffect, useCallback } from "react";
import { listTables, createTable } from "../../api/poker";
import type { PokerTableSummary, CreateTableRequest } from "../../api/pokerTypes";

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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Poker Lobby</h1>
        <button onClick={() => setShowCreate(true)} className="bg-ndai-600 hover:bg-ndai-700 text-white px-4 py-2 rounded-lg text-sm font-medium">Create Table</button>
      </div>
      {error && <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4">{error}</div>}
      {showCreate && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
          <form onSubmit={handleCreate} className="flex gap-4 items-end">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Big Blind</label>
              <input name="big_blind" type="number" defaultValue="200" className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-32" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Max Seats</label>
              <input name="max_seats" type="number" defaultValue="6" min="2" max="9" className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-20" />
            </div>
            <button type="submit" className="bg-ndai-600 hover:bg-ndai-700 text-white px-4 py-2 rounded-lg text-sm">Create</button>
            <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-gray-600 text-sm">Cancel</button>
          </form>
        </div>
      )}
      {loading ? <p className="text-gray-500">Loading...</p> : tables.length === 0 ? (
        <div className="text-center py-12 text-gray-400">No tables available. Create one!</div>
      ) : (
        <div className="grid gap-3">
          {tables.map(t => (
            <a key={t.id} href={`#/poker/table/${t.id}`} className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-ndai-300 transition-colors">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium text-gray-900">Table {t.id.slice(0, 8)}</span>
                  <span className="ml-3 text-sm text-gray-500">{t.small_blind}/{t.big_blind} blinds</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-600">{t.player_count}/{t.max_seats} players</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${t.status === "open" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>{t.status}</span>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
