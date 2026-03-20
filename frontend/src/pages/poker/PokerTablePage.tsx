import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { usePokerStream } from "../../hooks/usePokerStream";
import { getTableState, joinTable, submitAction, startHand } from "../../api/poker";
import { PokerTable } from "../../components/poker/PokerTable";
import type { TableView, PlayerActionRequest } from "../../api/pokerTypes";

export function PokerTablePage({ tableId }: { tableId: string }) {
  const { token } = useAuth();
  const userId = token ? JSON.parse(atob(token.split(".")[1])).sub : null;
  const { tableView: streamView, lastEvent, isConnected, connect, disconnect } = usePokerStream(tableId, token);
  const [tableView, setTableView] = useState<TableView | null>(null);
  const [showBuyIn, setShowBuyIn] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load initial state
  useEffect(() => {
    getTableState(tableId).then(setTableView).catch(() => {});
    connect();
    return () => disconnect();
  }, [tableId, connect, disconnect]);

  // Update from stream
  useEffect(() => {
    if (streamView) setTableView(streamView);
  }, [streamView]);

  // Refresh full state on significant events
  useEffect(() => {
    if (lastEvent && ["hand_start", "hand_end", "player_joined", "player_left", "showdown"].includes(lastEvent.type)) {
      getTableState(tableId).then(setTableView).catch(() => {});
    }
  }, [lastEvent, tableId]);

  const isSeated = tableView?.seats.some(s => s && s.player_id === userId) ?? false;

  const handleJoin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const buyIn = parseInt(fd.get("buy_in") as string) || 0;
    try {
      await joinTable(tableId, { buy_in: buyIn, wallet_address: "0x0000000000000000000000000000000000000000" });
      setShowBuyIn(false);
      getTableState(tableId).then(setTableView);
    } catch (e: any) {
      setError(e.detail || "Failed to join");
    }
  };

  const handleAction = useCallback(async (action: string, amount?: number) => {
    try {
      await submitAction(tableId, { action: action as any, amount });
      getTableState(tableId).then(setTableView);
    } catch (e: any) {
      setError(e.detail || "Action failed");
    }
  }, [tableId]);

  const handleStartHand = async () => {
    try {
      await startHand(tableId);
      getTableState(tableId).then(setTableView);
    } catch (e: any) {
      setError(e.detail || "Failed to start hand");
    }
  };

  return (
    <div className="h-full relative">
      {error && <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm z-50">{error}</div>}
      {!isConnected && <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-yellow-600 text-white px-4 py-2 rounded-lg text-sm z-50">Reconnecting...</div>}

      <PokerTable tableView={tableView} myPlayerId={userId} onAction={handleAction} />

      {/* Buy-in overlay */}
      {!isSeated && tableView && !showBuyIn && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40">
          <button onClick={() => setShowBuyIn(true)} className="bg-ndai-600 hover:bg-ndai-700 text-white px-8 py-3 rounded-lg font-medium text-lg shadow-xl">
            Sit Down
          </button>
        </div>
      )}

      {showBuyIn && tableView && (
        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-80">
            <h3 className="text-lg font-bold mb-4">Buy In</h3>
            <p className="text-sm text-gray-500 mb-3">Min: {tableView.min_buy_in} / Max: {tableView.max_buy_in}</p>
            <form onSubmit={handleJoin}>
              <input name="buy_in" type="number" defaultValue={tableView.min_buy_in} min={tableView.min_buy_in} max={tableView.max_buy_in} className="w-full px-3 py-2 border border-gray-300 rounded-lg mb-3" />
              <div className="flex gap-2">
                <button type="submit" className="flex-1 bg-ndai-600 hover:bg-ndai-700 text-white py-2 rounded-lg font-medium">Join</button>
                <button type="button" onClick={() => setShowBuyIn(false)} className="flex-1 border border-gray-300 py-2 rounded-lg text-gray-600">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Start hand button (if seated, no hand in progress, 2+ players) */}
      {isSeated && tableView && (!tableView.hand_number || tableView.phase === "waiting" || tableView.phase === "showdown" || tableView.phase === "settling") && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40">
          <button onClick={handleStartHand} className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-medium shadow-xl">
            Deal
          </button>
        </div>
      )}
    </div>
  );
}
