import React, { useState, useEffect } from "react";
import { listVulnAgreements, type VulnAgreementResponse } from "../../api/vulns";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";

export function DealsListPage() {
  const [deals, setDeals] = useState<VulnAgreementResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listVulnAgreements()
      .then(setDeals)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <h1 className="font-mono text-headline mb-6">MY DEALS</h1>

      {deals.length === 0 ? (
        <EmptyState message="No deals yet" />
      ) : (
        <div className="space-y-0">
          {deals.map((d) => (
            <a
              key={d.id}
              href={`#/deals/${d.id}`}
              className="block border-2 border-zk-border border-b-0 last:border-b-2 p-4
                         hover:bg-white no-underline text-zk-text"
            >
              <div className="flex items-center gap-4">
                <span className="font-mono text-sm font-bold flex-1 truncate">
                  {d.id.slice(0, 8)}...
                </span>
                {d.budget_cap && (
                  <span className="font-mono text-sm">{d.budget_cap} ETH</span>
                )}
                <StatusBadge status={d.status} />
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
