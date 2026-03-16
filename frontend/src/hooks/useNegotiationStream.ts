import { useState, useEffect, useRef, useCallback } from "react";

export type NegotiationPhase =
  | "started"
  | "seller_disclosure"
  | "buyer_evaluation"
  | "nash_resolution"
  | "complete"
  | "round";

interface UseNegotiationStreamResult {
  phase: NegotiationPhase | null;
  isComplete: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

export function useNegotiationStream(
  agreementId: string | null,
  token: string
): UseNegotiationStreamResult {
  const [phase, setPhase] = useState<NegotiationPhase | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const disconnect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!agreementId || !token) return;

    disconnect();

    // SSE doesn't support Authorization headers, pass token as query param
    const url = `/api/v1/negotiations/${agreementId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    const phases: NegotiationPhase[] = [
      "started",
      "seller_disclosure",
      "buyer_evaluation",
      "nash_resolution",
      "round",
      "complete",
    ];

    for (const p of phases) {
      es.addEventListener(p, () => {
        setPhase(p);
        if (p === "complete") {
          setIsComplete(true);
          es.close();
        }
      });
    }

    es.onerror = () => {
      // EventSource will auto-reconnect; if closed, just clean up
      if (es.readyState === EventSource.CLOSED) {
        setError("Connection lost");
      }
    };
  }, [agreementId, token, disconnect]);

  useEffect(() => {
    return disconnect;
  }, [disconnect]);

  return { phase, isComplete, error, connect, disconnect };
}
