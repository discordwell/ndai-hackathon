import { useState, useCallback, useRef, useEffect } from "react";
import type { TableView, GameEvent } from "../api/pokerTypes";
import { getTableState } from "../api/poker";

interface UsePokerStreamResult {
  tableView: TableView | null;
  lastEvent: GameEvent | null;
  isConnected: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

export function usePokerStream(
  tableId: string | null,
  token: string | null,
): UsePokerStreamResult {
  const [tableView, setTableView] = useState<TableView | null>(null);
  const [lastEvent, setLastEvent] = useState<GameEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced full-state refresh — coalesces rapid events
  const refreshState = useCallback(() => {
    if (!tableId) return;
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => {
      getTableState(tableId).then(setTableView).catch(() => {});
    }, 100);
  }, [tableId]);

  const disconnect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!tableId || !token) return;
    disconnect();

    const url = `/api/v1/poker/tables/${tableId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    // Initial full state from SSE
    es.addEventListener("game_state", (e) => {
      setTableView(JSON.parse(e.data));
      setIsConnected(true);
      setError(null);
    });

    // All game events trigger a state refresh
    const eventTypes = [
      "hand_start", "blinds_posted", "cards_dealt", "deal_hole_cards",
      "player_action", "phase_change", "action_on", "showdown",
      "hand_end", "player_timeout", "player_joined", "player_left",
      "settlement",
    ];
    for (const type of eventTypes) {
      es.addEventListener(type, (e) => {
        const data = JSON.parse(e.data);
        setLastEvent({ type, data });
        refreshState();
      });
    }

    es.onerror = () => {
      setError("Connection lost");
      setIsConnected(false);
      setTimeout(() => {
        if (esRef.current === es) connect();
      }, 3000);
    };
  }, [tableId, token, disconnect, refreshState]);

  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return { tableView, lastEvent, isConnected, error, connect, disconnect };
}
