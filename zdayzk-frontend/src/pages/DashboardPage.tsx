import React, { useState, useEffect } from "react";
import { listVulns, listVulnAgreements } from "../api/vulns";
import type { VulnResponse, VulnAgreementResponse } from "../api/types";
import { SeverityMeter } from "../components/marketplace/SeverityMeter";

export function DashboardPage() {
  const [vulns, setVulns] = useState<VulnResponse[]>([]);
  const [agreements, setAgreements] = useState<VulnAgreementResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      listVulns().catch(() => []),
      listVulnAgreements().catch(() => []),
    ]).then(([v, a]) => {
      setVulns(v);
      setAgreements(a);
      setLoading(false);
    });
  }, []);

  const activeListings = vulns.filter((v) => v.status === "active").length;
  const openDeals = agreements.filter((a) => ["pending", "running", "funded"].includes(a.status)).length;
  const completedDeals = agreements.filter((a) => a.status === "completed").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <h1 className="text-xl font-bold text-white mb-6">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Active Listings", value: activeListings, accent: true },
          { label: "Open Deals", value: openDeals },
          { label: "Completed", value: completedDeals },
          { label: "Total Activity", value: vulns.length + agreements.length },
        ].map((stat) => (
          <div key={stat.label} className="glass-card p-4">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{stat.label}</p>
            <p className={`text-2xl font-bold ${stat.accent ? "text-accent-400" : "text-white"}`}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      {/* My Submissions */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">My Submissions</h2>
          <a href="#/submit" className="text-xs text-accent-400 hover:underline">
            + Submit New
          </a>
        </div>
        {vulns.length === 0 ? (
          <div className="glass-card p-8 text-center">
            <p className="text-sm text-gray-500">No submissions yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {vulns.map((v) => (
              <div key={v.id} className="glass-card-hover p-4 flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">{v.target_software}</p>
                    <p className="text-xs text-gray-500 font-mono">{v.vulnerability_class}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-28">
                    <SeverityMeter cvss={v.cvss_self_assessed} />
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded border ${
                    v.status === "active"
                      ? "bg-success-500/20 text-success-400 border-success-500/30"
                      : "bg-surface-700 text-gray-400 border-surface-600"
                  }`}>
                    {v.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* My Deals */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">My Deals</h2>
          <a href="#/deals" className="text-xs text-accent-400 hover:underline">
            View All
          </a>
        </div>
        {agreements.length === 0 ? (
          <div className="glass-card p-8 text-center">
            <p className="text-sm text-gray-500">No deals yet</p>
            <a href="#/marketplace" className="text-xs text-accent-400 hover:underline mt-1 inline-block">
              Browse Marketplace
            </a>
          </div>
        ) : (
          <div className="space-y-2">
            {agreements.map((a) => (
              <a
                key={a.id}
                href={`#/deals/${a.id}`}
                className="glass-card-hover p-4 flex items-center justify-between"
              >
                <div>
                  <p className="text-sm font-mono text-gray-300">{a.id.slice(0, 12)}...</p>
                  <p className="text-xs text-gray-500">
                    Budget: {a.budget_cap?.toFixed(2) ?? "—"}
                  </p>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded border ${
                  a.status === "completed"
                    ? "bg-success-500/20 text-success-400 border-success-500/30"
                    : a.status === "running"
                    ? "bg-accent-400/20 text-accent-400 border-accent-400/30"
                    : "bg-surface-700 text-gray-400 border-surface-600"
                }`}>
                  {a.status}
                </span>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
