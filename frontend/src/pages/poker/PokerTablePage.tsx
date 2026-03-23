import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { usePokerStream } from "../../hooks/usePokerStream";
import { getTableState, joinTable, leaveTable, submitAction, startHand } from "../../api/poker";
import { PokerTable } from "../../components/poker/PokerTable";
import HandResultOverlay from "../../components/poker/HandResultOverlay";
import { VerificationPanel } from "../../components/shared/VerificationPanel";
import ActionLog from "../../components/poker/ActionLog";
import type { ActionEntry } from "../../components/poker/ActionLog";
import type { TableView } from "../../api/pokerTypes";

export function PokerTablePage({ tableId }: { tableId: string }) {
  const { token } = useAuth();
  let userId: string | null = null;
  try {
    userId = token ? JSON.parse(atob(token.split(".")[1])).sub : null;
  } catch {
    // Malformed token — will be null
  }
  const { tableView: streamView, lastEvent, isConnected, error: streamError, connect, disconnect } = usePokerStream(tableId, token);
  const [tableView, setTableView] = useState<TableView | null>(null);
  const [showBuyIn, setShowBuyIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionPending, setActionPending] = useState(false);
  const [handResult, setHandResult] = useState<any>(null);
  const [handVerification, setHandVerification] = useState<any>(null);
  const [showVerification, setShowVerification] = useState(false);
  const [actionLog, setActionLog] = useState<ActionEntry[]>([]);
  const [lastActions, setLastActions] = useState<Record<number, { action: string; amount: number }>>({});

  // Auto-dismiss errors
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(null), 4000);
      return () => clearTimeout(t);
    }
  }, [error]);

  // Load initial state and connect SSE
  useEffect(() => {
    getTableState(tableId).then(setTableView).catch(() => {});
    connect();
    return () => disconnect();
  }, [tableId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Update from stream (always take the latest)
  useEffect(() => {
    if (streamView) setTableView(streamView);
  }, [streamView]);

  // Derive friendly label for a player
  const playerLabel = useCallback((seatIdx: number | undefined, playerId?: string) => {
    if (playerId === userId) return "You";
    if (seatIdx !== undefined && seatIdx >= 0) return `Seat ${seatIdx}`;
    return playerId ? playerId.slice(0, 6) + "\u2026" : "?";
  }, [userId]);

  // Process SSE events for action log, hand results, verification
  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent.type === "player_action") {
      const seat = lastEvent.data?.seat;
      const action = lastEvent.data?.action;
      const amount = lastEvent.data?.amount ?? 0;

      // Find player_id from tableView seats
      const seatData = tableView?.seats[seat];
      const pid = seatData?.player_id;

      setActionLog(prev => [...prev, {
        seat,
        action,
        amount,
        playerLabel: playerLabel(seat, pid),
        timestamp: Date.now(),
      }]);

      setLastActions(prev => ({ ...prev, [seat]: { action, amount } }));

      // Auto-clear last action badge after 3s
      setTimeout(() => {
        setLastActions(prev => {
          const next = { ...prev };
          if (next[seat]?.action === action) delete next[seat];
          return next;
        });
      }, 3000);
    }

    if (lastEvent.type === "player_timeout") {
      const seat = lastEvent.data?.seat;
      setLastActions(prev => ({ ...prev, [seat]: { action: "timeout_fold", amount: 0 } }));
      setActionLog(prev => [...prev, {
        seat,
        action: "timeout_fold",
        amount: 0,
        playerLabel: playerLabel(seat),
        timestamp: Date.now(),
      }]);
    }

    if (lastEvent.type === "showdown" && lastEvent.data?.results?.length > 0) {
      const winner = lastEvent.data.results[0];
      const winnerId = winner.player_id;
      setHandResult({
        ...winner,
        displayName: playerLabel(winner.seat, winnerId),
      });
    }

    if (lastEvent.type === "hand_end" && lastEvent.data?.reason === "last_standing") {
      const winnerId = lastEvent.data.winner_player_id;
      const seat = lastEvent.data.winner_seat;
      setHandResult({
        player_id: winnerId,
        hand_rank: "Last standing",
        amount: lastEvent.data.amount,
        displayName: playerLabel(seat, winnerId),
      });
    }

    if (lastEvent.type === "hand_verification") {
      setHandVerification(lastEvent.data?.verification || null);
    }

    // Clear state when new hand starts
    if (lastEvent.type === "hand_start") {
      setHandVerification(null);
      setActionLog([]);
      setLastActions({});
      setShowVerification(false);
    }
  }, [lastEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  const isSeated = tableView?.seats.some(s => s && s.player_id === userId) ?? false;
  const isMyTurn = tableView?.action_on != null && tableView.seats[tableView.action_on]?.player_id === userId;
  const handActive = tableView?.phase && !["waiting", "showdown", "settling"].includes(tableView.phase);
  const canDeal = isSeated && !handActive && (tableView?.seats.filter(s => s != null).length ?? 0) >= 2;

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

  const handleLeave = async () => {
    try {
      await leaveTable(tableId);
      window.location.hash = "#/poker";
    } catch (e: any) {
      setError(e.detail || "Cannot leave during hand");
    }
  };

  const handleAction = useCallback(async (action: string, amount?: number) => {
    if (actionPending) return;
    setActionPending(true);
    try {
      await submitAction(tableId, { action: action as any, amount });
      getTableState(tableId).then(setTableView);
    } catch (e: any) {
      setError(e.detail || "Action failed");
    } finally {
      setActionPending(false);
    }
  }, [tableId, actionPending]);

  const handleStartHand = async () => {
    try {
      await startHand(tableId);
      getTableState(tableId).then(setTableView);
    } catch (e: any) {
      setError(e.detail || "Failed to start hand");
    }
  };

  return (
    <div className="h-full relative" style={{ minHeight: "calc(100vh - 40px)" }}>
      {/* Top bar */}
      <div className="absolute top-2 right-4 z-40 flex items-center gap-2">
        {handVerification && (
          <button
            onClick={() => setShowVerification(!showVerification)}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-all ${
              showVerification
                ? "bg-emerald-600 text-white"
                : "bg-gray-800 hover:bg-gray-700 text-emerald-400 border border-emerald-500/30"
            }`}
          >
            &#x1F512; TEE Verified
          </button>
        )}
        {isSeated && (
          <button onClick={handleLeave} className="bg-gray-800 hover:bg-gray-700 text-gray-300 px-4 py-1.5 rounded text-sm">
            Leave Table
          </button>
        )}
      </div>

      {/* Error / connection status */}
      {error && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm z-50">
          {error}
        </div>
      )}
      {!isConnected && !error && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-yellow-600 text-white px-4 py-2 rounded-lg text-sm z-50">
          Reconnecting...
        </div>
      )}

      {/* Poker table */}
      <PokerTable tableView={tableView} myPlayerId={userId} onAction={handleAction} lastActions={lastActions} />

      {/* Action log — bottom right */}
      {actionLog.length > 0 && (
        <div className="absolute bottom-4 right-4 z-40 w-64">
          <ActionLog actions={actionLog} />
        </div>
      )}

      {/* Verification panel — slide-out drawer from right */}
      {showVerification && handVerification && (
        <div className="absolute top-12 right-4 z-40 w-96 max-h-[70vh] overflow-y-auto shadow-2xl rounded-xl animate-[fadeSlideUp_0.2s_ease-out]">
          <VerificationPanel verification={handVerification} />
        </div>
      )}

      {/* Sit Down button */}
      {!isSeated && tableView && !showBuyIn && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40">
          <button onClick={() => setShowBuyIn(true)} className="bg-ndai-600 hover:bg-ndai-700 text-white px-8 py-3 rounded-lg font-medium text-lg shadow-xl">
            Sit Down
          </button>
        </div>
      )}

      {/* Buy-in dialog */}
      {showBuyIn && tableView && (
        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-80">
            <h3 className="text-lg font-bold mb-4">Buy In</h3>
            <p className="text-sm text-gray-500 mb-3">
              Blinds: {tableView.small_blind}/{tableView.big_blind} &middot; Buy-in: {tableView.min_buy_in} - {tableView.max_buy_in}
            </p>
            <form onSubmit={handleJoin}>
              <input name="buy_in" type="number" defaultValue={tableView.min_buy_in} min={tableView.min_buy_in} max={tableView.max_buy_in}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg mb-3 focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none" />
              <div className="flex gap-2">
                <button type="submit" className="flex-1 bg-ndai-600 hover:bg-ndai-700 text-white py-2 rounded-lg font-medium">Join</button>
                <button type="button" onClick={() => setShowBuyIn(false)} className="flex-1 border border-gray-300 py-2 rounded-lg text-gray-600">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Hand result overlay */}
      <HandResultOverlay result={handResult} onDismiss={() => setHandResult(null)} />

      {/* Deal button — positioned above action log area */}
      {canDeal && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40">
          <button onClick={handleStartHand} className="bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-medium shadow-xl">
            Deal
          </button>
        </div>
      )}
    </div>
  );
}
