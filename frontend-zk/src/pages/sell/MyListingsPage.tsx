import React, { useState, useEffect } from "react";
import { listVulns, type VulnResponse } from "../../api/vulns";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";

export function MyListingsPage() {
  const [vulns, setVulns] = useState<VulnResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listVulns()
      .then(setVulns)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <h1 className="font-mono text-headline">MY LISTINGS</h1>
        <a href="#/sell/new" className="zk-btn no-underline">+ NEW</a>
      </div>

      {vulns.length === 0 ? (
        <EmptyState
          message="No vulnerabilities posted yet"
          action={<a href="#/sell/new" className="zk-btn-accent no-underline">POST YOUR FIRST</a>}
        />
      ) : (
        <div className="space-y-0">
          {vulns.map((v) => (
            <div key={v.id} className="border-2 border-zk-border border-b-0 last:border-b-2 p-4">
              <div className="flex items-center gap-4">
                <span className="font-mono text-sm font-bold flex-1">
                  {v.target_software} <span className="text-zk-muted font-normal">v{v.target_version}</span>
                </span>
                <span className="font-mono text-xs text-zk-muted">{v.vulnerability_class}</span>
                <span className="font-mono text-xs">{v.impact_type}</span>
                <span className="font-mono text-sm font-bold">{v.cvss_self_assessed.toFixed(1)}</span>
                <StatusBadge status={v.status} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
