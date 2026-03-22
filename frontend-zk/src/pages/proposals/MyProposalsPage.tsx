import React, { useState, useEffect } from "react";
import { getMyProposals } from "../../api/proposals";
import type { Proposal } from "../../api/types";

const STATUS_STYLES: Record<string, string> = {
  draft: "text-zk-muted border-zk-border",
  pending: "text-zk-muted border-zk-border",
  deposited: "text-blue-700 border-blue-600",
  building: "text-zk-accent border-zk-accent",
  verifying: "text-zk-accent border-zk-accent",
  passed: "text-emerald-700 border-emerald-600",
  failed: "text-red-700 border-red-600",
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
        <div className="w-6 h-6 border-3 border-zk-border border-t-zk-text animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-mono font-extrabold text-zk-text uppercase">My Proposals</h1>
          <p className="text-xs text-zk-muted font-mono mt-1">
            {proposals.length} {proposals.length === 1 ? "proposal" : "proposals"}
          </p>
        </div>
        <a
          href="#/targets"
          className="px-4 py-2 bg-zk-text text-white font-mono font-bold text-xs uppercase tracking-wider hover:bg-zk-accent transition-colors"
        >
          New Proposal
        </a>
      </div>

      {error && (
        <div className="border-3 border-red-600 bg-red-50 p-4 text-red-700 text-sm font-mono mb-6">
          {error}
        </div>
      )}

      {proposals.length === 0 ? (
        <div className="border-3 border-zk-border bg-white p-12 text-center">
          <p className="text-zk-muted text-sm font-mono mb-3">No proposals yet.</p>
          <a
            href="#/targets"
            className="text-zk-accent hover:text-zk-text text-xs font-mono font-bold uppercase underline"
          >
            Browse verification targets
          </a>
        </div>
      ) : (
        <div className="border-3 border-zk-border bg-white overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b-2 border-zk-border">
                <th className="text-left text-[10px] text-zk-dim font-mono uppercase tracking-wider px-4 py-3">Target</th>
                <th className="text-left text-[10px] text-zk-dim font-mono uppercase tracking-wider px-4 py-3">Capability</th>
                <th className="text-left text-[10px] text-zk-dim font-mono uppercase tracking-wider px-4 py-3">Status</th>
                <th className="text-left text-[10px] text-zk-dim font-mono uppercase tracking-wider px-4 py-3">Price</th>
                <th className="text-left text-[10px] text-zk-dim font-mono uppercase tracking-wider px-4 py-3">Date</th>
                <th className="text-right text-[10px] text-zk-dim font-mono uppercase tracking-wider px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-zk-border hover:bg-zk-bg transition-colors"
                >
                  <td className="px-4 py-3 text-sm text-zk-text font-mono font-bold">{p.target_name}</td>
                  <td className="px-4 py-3 text-xs text-zk-muted font-mono">{p.claimed_capability}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 border-2 uppercase ${
                        STATUS_STYLES[p.status] || STATUS_STYLES.pending
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-zk-accent font-mono font-bold">{p.asking_price_eth} ETH</td>
                  <td className="px-4 py-3 text-xs text-zk-muted font-mono">
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <a
                      href={`#/proposals/${p.id}`}
                      className="text-xs text-zk-accent hover:text-zk-text font-mono font-bold uppercase underline"
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
