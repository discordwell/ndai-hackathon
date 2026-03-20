import React, { useState } from "react";

interface VerificationEvent {
  event_type: string;
  timestamp: string;
  data_hash: string;
  description: string;
}

interface VerificationData {
  session_id: string;
  events: VerificationEvent[];
  chain_hashes: string[];
  final_hash: string;
  attestation_claims: string[];
}

interface Props {
  verification: VerificationData | null | undefined;
}

export function VerificationPanel({ verification }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!verification) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <span className="text-green-600 text-lg">&#x2713;</span>
          <h3 className="font-semibold text-gray-900">Verification Chain</h3>
        </div>
        <span className="text-xs text-gray-400">{expanded ? "collapse" : "expand"}</span>
      </button>

      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs text-gray-500">Session</span>
        <code className="text-xs bg-gray-50 px-2 py-0.5 rounded font-mono text-gray-600">
          {verification.session_id.slice(0, 12)}...
        </code>
        <span className="text-xs text-gray-500 ml-2">Final hash</span>
        <code className="text-xs bg-gray-50 px-2 py-0.5 rounded font-mono text-gray-600">
          {verification.final_hash.slice(0, 16)}...
        </code>
      </div>

      {verification.attestation_claims.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {verification.attestation_claims.map((claim, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-green-500 text-sm mt-0.5">&#x2713;</span>
              <span className="text-sm text-gray-700">{claim}</span>
            </div>
          ))}
        </div>
      )}

      {expanded && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Event Timeline
          </h4>
          <div className="space-y-2">
            {verification.events.map((event, i) => (
              <div key={i} className="flex items-start gap-3 text-xs">
                <div className="w-2 h-2 bg-ndai-400 rounded-full mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{event.event_type}</span>
                    <span className="text-gray-400">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-gray-600 mt-0.5">{event.description}</p>
                  <code className="text-[10px] text-gray-400 font-mono">
                    hash: {event.data_hash.slice(0, 16)}...
                    {verification.chain_hashes[i] && (
                      <> | chain: {verification.chain_hashes[i].slice(0, 16)}...</>
                    )}
                  </code>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
