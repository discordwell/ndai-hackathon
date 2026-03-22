import React, { useState, useEffect } from "react";
import { listMyRFPs, type RFPResponse } from "../../api/rfps";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { EmptyState } from "../../components/EmptyState";
import { StatusBadge } from "../../components/StatusBadge";

export function MyRFPsPage() {
  const [rfps, setRFPs] = useState<RFPResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMyRFPs()
      .then(setRFPs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <h1 className="font-mono text-headline">MY RFPS</h1>
        <a href="#/buy/new" className="zk-btn-accent no-underline">+ NEW RFP</a>
      </div>

      {rfps.length === 0 ? (
        <EmptyState
          message="No RFPs posted yet"
          action={<a href="#/buy/new" className="zk-btn-accent no-underline">POST YOUR FIRST</a>}
        />
      ) : (
        <div className="space-y-0">
          {rfps.map((r) => (
            <a
              key={r.id}
              href={`#/buy/rfp/${r.id}`}
              className="block border-2 border-zk-border border-b-0 last:border-b-2 p-4
                         hover:bg-white no-underline text-zk-text"
            >
              <div className="flex items-center gap-4">
                <span className="font-mono text-sm font-bold flex-1 truncate">{r.title}</span>
                <span className="font-mono text-xs text-zk-muted">{r.target_software}</span>
                <span className="font-mono text-xs">{r.desired_capability}</span>
                <span className="font-mono text-sm font-bold">{r.budget_min_eth}-{r.budget_max_eth} ETH</span>
                <StatusBadge status={r.status} />
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
