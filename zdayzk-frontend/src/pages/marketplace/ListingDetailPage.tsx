import React, { useState, useEffect } from "react";
import { getVuln, createVulnAgreement } from "../../api/vulns";
import type { VulnResponse } from "../../api/types";
import { SeverityMeter } from "../../components/marketplace/SeverityMeter";

export function ListingDetailPage({ id }: { id: string }) {
  const [vuln, setVuln] = useState<VulnResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [budgetCap, setBudgetCap] = useState("0.5");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    getVuln(id)
      .then(setVuln)
      .catch((e) => setError(e.detail || "Failed to load vulnerability"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleProposeDeal() {
    setCreating(true);
    setCreateError("");
    try {
      const agreement = await createVulnAgreement({
        vulnerability_id: id,
        budget_cap: parseFloat(budgetCap),
      });
      window.location.hash = `#/deals/${agreement.id}`;
    } catch (err: any) {
      setCreateError(err.detail || "Failed to create agreement");
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !vuln) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-danger-400 text-sm">{error || "Vulnerability not found"}</p>
        <a href="#/marketplace" className="text-xs text-accent-400 hover:underline mt-2 inline-block">
          Back to Marketplace
        </a>
      </div>
    );
  }

  return (
    <div className="animate-fade-in max-w-3xl">
      <a href="#/marketplace" className="text-xs text-gray-500 hover:text-gray-300 transition-colors mb-4 inline-block">
        &larr; Back to Marketplace
      </a>

      <div className="glass-card p-8">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white">{vuln.target_software}</h1>
            <p className="text-sm text-gray-500 font-mono mt-1">{vuln.target_version}</p>
          </div>
          <span className="text-xs font-medium px-3 py-1 rounded bg-surface-700 text-gray-300 border border-surface-600">
            {vuln.impact_type}
          </span>
        </div>

        <div className="mb-6">
          <SeverityMeter cvss={vuln.cvss_self_assessed} />
        </div>

        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-surface-800/50 rounded-lg p-3">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Class</span>
            <p className="text-sm text-gray-300 mt-1 font-mono">{vuln.vulnerability_class}</p>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-3">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Patch Status</span>
            <p className="text-sm text-gray-300 mt-1">{vuln.patch_status}</p>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-3">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Exclusivity</span>
            <p className="text-sm text-gray-300 mt-1">{vuln.exclusivity}</p>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-3">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Status</span>
            <p className="text-sm text-gray-300 mt-1">{vuln.status}</p>
          </div>
        </div>

        {/* Propose Deal */}
        <div className="border-t border-surface-700/50 pt-6">
          <h2 className="text-sm font-semibold text-white mb-4">Propose Deal</h2>

          {createError && (
            <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-3 rounded-lg mb-4">
              {createError}
            </div>
          )}

          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="block text-[11px] text-gray-500 mb-1.5">Budget Cap (normalized 0-1)</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={budgetCap}
                onChange={(e) => setBudgetCap(e.target.value)}
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50 transition-colors"
              />
            </div>
            <button
              onClick={handleProposeDeal}
              disabled={creating}
              className="px-6 py-2 bg-accent-400 text-surface-950 font-medium rounded-lg hover:bg-accent-300 disabled:opacity-50 transition-colors text-sm"
            >
              {creating ? "Creating..." : "Propose Deal"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
