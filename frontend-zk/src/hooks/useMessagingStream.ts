/**
 * SSE hook for real-time message delivery.
 * Connects to /api/v1/messaging/stream and dispatches events.
 */
import { useState, useCallback, useRef, useEffect } from "react";

export interface IncomingMessage {
  conversation_id: string;
  message_id: string;
  sender_pubkey: string;
  header: string;
  ciphertext: string;
  x3dh_header: string | null;
  message_index: number;
  created_at: string;
}

interface UseMessagingStreamResult {
  isConnected: boolean;
  error: string | null;
  lastMessage: IncomingMessage | null;
  prekeyLow: boolean;
  connect: () => void;
  disconnect: () => void;
}

export function useMessagingStream(): UseMessagingStreamResult {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<IncomingMessage | null>(null);
  const [prekeyLow, setPrekeyLow] = useState(false);
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
    const token = sessionStorage.getItem("zdayzk_token");
    if (!token) return;

    const url = `/api/v1/messaging/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    es.onerror = () => {
      setError("Message stream disconnected");
      setIsConnected(false);
    };

    es.addEventListener("new_message", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as IncomingMessage;
      setLastMessage(data);
    });

    es.addEventListener("prekey_low", (e) => {
      setPrekeyLow(true);
    });
  }, [disconnect]);

  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return { isConnected, error, lastMessage, prekeyLow, connect, disconnect };
}
