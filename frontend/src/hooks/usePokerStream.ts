import { useState, useCallback, useRef, useEffect } from "react";
import type { TableView, GameEvent } from "../api/pokerTypes";

interface UsePokerStreamResult {
  tableView: TableView | null;
  lastEvent: GameEvent | null;
  isConnected: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

export function usePokerStream(tableId: string | null, token: string | null): UsePokerStreamResult {
  const [tableView, setTableView] = useState<TableView | null>(null);
  const [lastEvent, setLastEvent] = useState<GameEvent | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const disconnect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!tableId || !token) return;
    disconnect();

    const url = `/api/v1/poker/tables/${tableId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("game_state", (e) => {
      const data = JSON.parse(e.data);
      setTableView(data);
      setIsConnected(true);
      setError(null);
    });

    // All other event types - update table view fields incrementally
    const eventTypes = [
      "hand_start", "blinds_posted", "cards_dealt", "deal_hole_cards",
      "player_action", "phase_change", "action_on", "showdown",
      "hand_end", "player_timeout", "player_joined", "player_left"
    ];
    for (const type of eventTypes) {
      es.addEventListener(type, (e) => {
        const data = JSON.parse(e.data);
        setLastEvent({ type, data });
        // For phase_change, update community cards
        if (type === "phase_change" && data.community_cards) {
          setTableView(prev => prev ? { ...prev, community_cards: data.community_cards, phase: data.phase } : prev);
        }
        // For deal_hole_cards, update the hero's cards
        if (type === "deal_hole_cards" && data.hole_cards) {
          setTableView(prev => {
            if (!prev) return prev;
            // We need a full refresh for complex state updates
            return prev;
          });
        }
      });
    }

    es.onerror = () => {
      setError("Connection lost");
      setIsConnected(false);
      // Auto-reconnect after 3 seconds
      setTimeout(() => {
        if (esRef.current === es) connect();
      }, 3000);
    };
  }, [tableId, token, disconnect]);

  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return { tableView, lastEvent, isConnected, error, connect, disconnect };
}
