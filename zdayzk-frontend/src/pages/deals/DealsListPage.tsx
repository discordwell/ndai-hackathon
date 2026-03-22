import React, { useState, useEffect } from "react";
import { listVulnAgreements } from "../../api/vulns";
import type { VulnAgreementResponse } from "../../api/types";

export function DealsListPage() {
  const [deals, setDeals] = useState<VulnAgreementResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listVulnAgreements()
      .then(setDeals)
      .catch(() => {})
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
      <h1 className="text-xl font-bold text-white mb-6">My Deals</h1>

      {deals.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-sm text-gray-500 mb-2">No deals yet</p>
          <a href="#/marketplace" className="text-xs text-accent-400 hover:underline">
            Browse Marketplace
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {deals.map((deal) => (
            <a
              key={deal.id}
              href={`#/deals/${deal.id}`}
              className="glass-card-hover p-5 flex items-center justify-between"
            >
              <div>
                <p className="text-sm font-mono text-gray-300">
                  {deal.id.slice(0, 16)}...
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Vuln: {deal.vulnerability_id.slice(0, 12)}... &middot; Budget: {deal.budget_cap?.toFixed(2) ?? "—"}
                </p>
              </div>
              <span
                className={`text-[10px] px-2.5 py-1 rounded border font-medium ${
                  deal.status === "completed"
                    ? "bg-success-500/20 text-success-400 border-success-500/30"
                    : deal.status === "running"
                    ? "bg-accent-400/20 text-accent-400 border-accent-400/30"
                    : deal.status === "rejected"
                    ? "bg-danger-500/20 text-danger-400 border-danger-500/30"
                    : "bg-surface-700 text-gray-400 border-surface-600"
                }`}
              >
                {deal.status}
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
