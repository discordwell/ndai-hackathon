import React, { useState } from "react";
import { CopyButton } from "./CopyButton";

interface EgressEntry {
  timestamp: string;
  endpoint: string;
  method: string;
  request_bytes: number;
  response_bytes: number;
  request_hash: string;
  response_hash: string;
}

interface Props {
  entries: EgressEntry[] | null | undefined;
}

export function EgressLogDisplay({ entries, defaultExpanded = true }: Props & { defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (!entries || entries.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <span className="text-ndai-600 text-lg">&#x2194;</span>
          <h3 className="font-semibold text-gray-900">Egress Log</h3>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
            {entries.length} call{entries.length !== 1 ? "s" : ""}
          </span>
        </div>
        <span className="text-xs text-gray-400">{expanded ? "collapse" : "expand"}</span>
      </button>

      {expanded && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 pr-3 font-semibold text-gray-500 uppercase tracking-wide">
                  Endpoint
                </th>
                <th className="text-right py-2 px-3 font-semibold text-gray-500 uppercase tracking-wide">
                  Req
                </th>
                <th className="text-right py-2 px-3 font-semibold text-gray-500 uppercase tracking-wide">
                  Resp
                </th>
                <th className="text-left py-2 px-3 font-semibold text-gray-500 uppercase tracking-wide">
                  Req Hash
                </th>
                <th className="text-left py-2 pl-3 font-semibold text-gray-500 uppercase tracking-wide">
                  Time
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 pr-3">
                    <code className="font-mono text-gray-700">{entry.endpoint}</code>
                  </td>
                  <td className="py-2 px-3 text-right text-gray-600">
                    {formatBytes(entry.request_bytes)}
                  </td>
                  <td className="py-2 px-3 text-right text-gray-600">
                    {formatBytes(entry.response_bytes)}
                  </td>
                  <td className="py-2 px-3">
                    <CopyButton value={entry.request_hash} truncateLength={12} />
                  </td>
                  <td className="py-2 pl-3 text-gray-400">
                    {new Date(entry.timestamp).toLocaleTimeString()}
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

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  return `${(bytes / 1024).toFixed(1)}KB`;
}
