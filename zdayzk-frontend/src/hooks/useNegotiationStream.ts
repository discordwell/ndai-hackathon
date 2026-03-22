import { useState, useCallback, useRef, useEffect } from "react";

export interface NegotiationEvent {
  phase: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface VulnOutcome {
  outcome: string;
  final_price: number | null;
  disclosure_level: number | null;
  reason: string | null;
  negotiation_rounds: number | null;
}

interface UseNegotiationStreamResult {
  events: NegotiationEvent[];
  outcome: VulnOutcome | null;
  isConnected: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

export function useNegotiationStream(agreementId: string): UseNegotiationStreamResult {
  const [events, setEvents] = useState<NegotiationEvent[]>([]);
  const [outcome, setOutcome] = useState<VulnOutcome | null>(null);
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
    disconnect();
    const token = localStorage.getItem("zdayzk_token");
    if (!token || !agreementId) return;

    const url = `/api/v1/vulns/negotiations/${agreementId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    es.onerror = () => {
      setError("Connection lost — retrying...");
      setIsConnected(false);
    };

    const addEvent = (phase: string, data: Record<string, unknown>) => {
      setEvents((prev) => [...prev, { phase, data, timestamp: Date.now() }]);
    };

    es.addEventListener("started", (e) => {
      addEvent("started", JSON.parse((e as MessageEvent).data));
    });

    es.addEventListener("seller_disclosure", (e) => {
      addEvent("seller_disclosure", JSON.parse((e as MessageEvent).data));
    });

    es.addEventListener("buyer_evaluation", (e) => {
      addEvent("buyer_evaluation", JSON.parse((e as MessageEvent).data));
    });

    es.addEventListener("nash_resolution", (e) => {
      addEvent("nash_resolution", JSON.parse((e as MessageEvent).data));
    });

    es.addEventListener("round", (e) => {
      addEvent("round", JSON.parse((e as MessageEvent).data));
    });

    es.addEventListener("complete", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      addEvent("complete", data);
      setOutcome(data as VulnOutcome);
      es.close();
      setIsConnected(false);
    });

    es.addEventListener("error_event", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      addEvent("error", data);
      setError(data.message || "Negotiation error");
      es.close();
      setIsConnected(false);
    });
  }, [agreementId, disconnect]);

  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return { events, outcome, isConnected, error, connect, disconnect };
}
