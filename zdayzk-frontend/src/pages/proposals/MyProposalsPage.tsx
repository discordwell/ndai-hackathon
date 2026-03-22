import React, { useState, useEffect } from "react";
import { getMyProposals } from "../../api/proposals";
import type { Proposal } from "../../api/types";

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-surface-700 text-gray-400 border-surface-600",
  pending: "bg-surface-700 text-gray-400 border-surface-600",
  deposited: "bg-info-500/20 text-info-400 border-info-500/30",
  building: "bg-accent-400/20 text-accent-400 border-accent-400/30",
  verifying: "bg-accent-400/20 text-accent-400 border-accent-400/30",
  passed: "bg-success-500/20 text-success-400 border-success-500/30",
  failed: "bg-danger-500/20 text-danger-400 border-danger-500/30",
};

export function MyProposalsPage() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getMyProposals()
      .then(setProposals)
      .catch((e) => setError(e.detail || "Failed to load proposals"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">My Proposals</h1>
          <p className="text-xs text-gray-500 mt-1">
            {proposals.length} {proposals.length === 1 ? "proposal" : "proposals"}
          </p>
        </div>
        <a
          href="#/targets"
          className="px-4 py-2 bg-accent-400 text-surface-950 font-medium rounded-lg hover:bg-accent-300 transition-colors text-xs"
        >
          New Proposal
        </a>
      </div>

      {error && (
        <div className="glass-card p-4 border-danger-500/30 text-danger-400 text-sm mb-6">
          {error}
        </div>
      )}

      {proposals.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-gray-400 text-sm mb-3">No proposals yet.</p>
          <a
            href="#/targets"
            className="text-accent-400 hover:text-accent-300 text-xs underline"
          >
            Browse verification targets
          </a>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-700/50">
                <th className="text-left text-[10px] text-gray-600 uppercase tracking-wider px-4 py-3">Target</th>
                <th className="text-left text-[10px] text-gray-600 uppercase tracking-wider px-4 py-3">Capability</th>
                <th className="text-left text-[10px] text-gray-600 uppercase tracking-wider px-4 py-3">Status</th>
                <th className="text-left text-[10px] text-gray-600 uppercase tracking-wider px-4 py-3">Price</th>
                <th className="text-left text-[10px] text-gray-600 uppercase tracking-wider px-4 py-3">Date</th>
                <th className="text-right text-[10px] text-gray-600 uppercase tracking-wider px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-surface-700/30 hover:bg-surface-800/50 transition-colors"
                >
                  <td className="px-4 py-3 text-sm text-white">{p.target_name}</td>
                  <td className="px-4 py-3 text-xs text-gray-400 font-mono">{p.claimed_capability}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-[10px] font-medium px-2 py-0.5 rounded border ${
                        STATUS_STYLES[p.status] || STATUS_STYLES.pending
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-accent-400 font-mono">{p.asking_price_eth} ETH</td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <a
                      href={`#/proposals/${p.id}`}
                      className="text-xs text-accent-400 hover:text-accent-300 underline"
                    >
                      View
                    </a>
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
