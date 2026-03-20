import React, { useEffect, useState } from "react";
import { getAccessLog, AccessLogEntry } from "../../api/secrets";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";

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
    case "error":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

export function AccessLogPage({ id }: Props) {
  const [log, setLog] = useState<AccessLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getAccessLog(id)
      .then(setLog)
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
        <p className="text-sm text-gray-500 mt-1">Secret ID: {id}</p>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : log.length === 0 ? (
        <EmptyState
          title="No access attempts yet"
          description="Access log entries will appear here when someone uses this secret"
        />
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Time
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Requester
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Action
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Result
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {log.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                    {entry.requester_id.slice(0, 12)}...
                  </td>
                  <td className="px-4 py-3 text-gray-900 max-w-xs truncate">
                    {entry.action_requested}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full font-medium ${statusColor(entry.status)}`}
                    >
                      {entry.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">
                    {entry.result_summary || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
