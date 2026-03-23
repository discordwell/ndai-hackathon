import React, { useEffect, useState } from "react";
import { getAccessLog, getSecret, AccessLogEntry, SecretResponse } from "../../api/secrets";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";
import { PolicyDisplay } from "../../components/shared/PolicyDisplay";
import { VerificationPanel } from "../../components/shared/VerificationPanel";
import { EgressLogDisplay } from "../../components/shared/EgressLogDisplay";

interface Props {
  id: string;
}

function statusColor(status: string) {
  switch (status) {
    case "approved":
    case "granted":
    case "success":
      return "bg-green-100 text-green-700";
    case "denied":
    case "failed":
      return "bg-red-100 text-red-700";
    case "error":
      return "bg-amber-100 text-amber-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

export function AccessLogPage({ id }: Props) {
  const [log, setLog] = useState<AccessLogEntry[]>([]);
  const [secret, setSecret] = useState<SecretResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([getAccessLog(id), getSecret(id)])
      .then(([logData, secretData]) => {
        setLog(logData);
        setSecret(secretData);
      })
      .catch((err: any) => setError(err.detail || err.message || "Failed to load access log"))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <div>
      <div className="mb-6">
        <a href="#/recall" className="text-sm text-ndai-600 hover:underline">
          &larr; Back to My Secrets
        </a>
        <h1 className="text-2xl font-bold mt-2">Access Log</h1>
        {secret && (
          <p className="text-sm text-gray-500 mt-1">{secret.name}</p>
        )}
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : log.length === 0 ? (
        <EmptyState
          title="No access attempts yet"
          description="Every access attempt will be logged here with full cryptographic verification data — approved, denied, or errored."
        />
      ) : (
        <div className="space-y-3">
          {log.map((entry) => {
            const isExpanded = expandedId === entry.id;
            const hasVerification = entry.verification_data != null;
            return (
              <div key={entry.id} className="bg-white rounded-xl border border-gray-100 overflow-hidden">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  className="w-full px-5 py-4 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 min-w-0">
                      <span className={`shrink-0 text-xs px-2 py-1 rounded-full font-medium ${statusColor(entry.status)}`}>
                        {entry.status}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {entry.action_requested}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {entry.requester_display_name || entry.requester_id.slice(0, 12) + "..."}
                          {" \u00b7 "}
                          {new Date(entry.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-4">
                      {hasVerification && (
                        <span className="text-xs text-ndai-600 font-medium">verified</span>
                      )}
                      <svg
                        className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-gray-100 pt-4 space-y-4">
                    {entry.result_summary && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Result Summary</h4>
                        <div className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-3 font-mono">
                          {entry.result_summary}
                        </div>
                      </div>
                    )}

                    {hasVerification && (
                      <div className="space-y-3">
                        <PolicyDisplay
                          report={entry.verification_data.policy_report}
                          constraints={entry.verification_data.policy_constraints}
                          defaultExpanded={false}
                        />
                        <VerificationPanel
                          verification={entry.verification_data.verification}
                          defaultExpanded={false}
                        />
                        <EgressLogDisplay
                          entries={entry.verification_data.egress_log}
                          defaultExpanded={false}
                        />
                      </div>
                    )}

                    {!hasVerification && !entry.result_summary && (
                      <p className="text-sm text-gray-400 italic">No additional data for this entry.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
