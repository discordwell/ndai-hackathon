import React, { useRef, useEffect } from "react";
import type { NegotiationEvent } from "../../hooks/useNegotiationStream";

interface Props {
  events: NegotiationEvent[];
  isConnected: boolean;
}

export function NegotiationLive({ events, isConnected }: Props) {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="glass-card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-surface-700/50">
        <span className="text-[10px] font-mono text-gray-500 uppercase tracking-wider">
          Event Log
        </span>
        <span className="flex items-center gap-1.5 text-[10px]">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isConnected ? "bg-success-400 animate-pulse" : "bg-gray-600"
            }`}
          />
          <span className={isConnected ? "text-success-400" : "text-gray-500"}>
            {isConnected ? "Live" : "Disconnected"}
          </span>
        </span>
      </div>
      <div
        ref={logRef}
        className="h-48 overflow-y-auto p-3 font-mono text-[11px] space-y-1"
      >
        {events.length === 0 ? (
          <p className="text-gray-600">Waiting for events...</p>
        ) : (
          events.map((evt, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-gray-600 flex-shrink-0">
                {new Date(evt.timestamp).toLocaleTimeString()}
              </span>
              <span className="text-accent-500">[{evt.phase}]</span>
              <span className="text-gray-400 truncate">
                {JSON.stringify(evt.data).slice(0, 120)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
