import React, { useState } from "react";
import { CopyButton } from "./CopyButton";

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
  escrowData?: {
    escrow_address: string;
    state?: string;
    attestation_hash?: string;
    balance_wei?: number;
    deadline?: number;
    blockchain_unavailable?: boolean;
  } | null;
}

export function VerificationPanel({ verification, escrowData, defaultExpanded = true }: Props & { defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (!verification && !escrowData) return null;

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

      {verification && expanded && (
        <>
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">Session</span>
            <CopyButton value={verification.session_id} truncateLength={12} />
            <span className="text-xs text-gray-500 ml-2">Final hash</span>
            <CopyButton value={verification.final_hash} truncateLength={16} />
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
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-gray-400">hash:</span>
                        <CopyButton value={event.data_hash} truncateLength={16} />
                        {verification.chain_hashes[i] && (
                          <>
                            <span className="text-[10px] text-gray-400">chain:</span>
                            <CopyButton value={verification.chain_hashes[i]} truncateLength={16} />
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
        </>
      )}

      {escrowData && !escrowData.blockchain_unavailable && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            On-Chain Settlement
          </h4>
          <div className="space-y-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Escrow</span>
              <a
                href={`https://sepolia.basescan.org/address/${escrowData.escrow_address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-ndai-600 hover:text-ndai-700"
              >
                {escrowData.escrow_address.slice(0, 10)}...{escrowData.escrow_address.slice(-6)}
              </a>
            </div>
            {escrowData.state && (
              <div className="flex items-center gap-2">
                <span className="text-gray-500">State</span>
                <span className="font-medium text-gray-900">{escrowData.state}</span>
              </div>
            )}
            {escrowData.attestation_hash && (
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Attestation Hash</span>
                <code className="bg-gray-50 px-2 py-0.5 rounded font-mono text-gray-600">
                  {escrowData.attestation_hash.slice(0, 18)}...
                </code>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
