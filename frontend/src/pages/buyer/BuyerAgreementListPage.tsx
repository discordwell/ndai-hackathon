import React from "react";
import { Card } from "../../components/shared/Card";
import { EmptyState } from "../../components/shared/EmptyState";
import { ListSkeleton } from "../../components/shared/Skeleton";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { useAgreements } from "../../hooks/useAgreements";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function BuyerAgreementListPage() {
  const { agreements, loading, error } = useAgreements();

  const sorted = [...agreements].sort(
    (a, b) => (b.created_at || "").localeCompare(a.created_at || "")
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">My Agreements</h1>
      {loading ? (
        <ListSkeleton />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : agreements.length === 0 ? (
        <EmptyState
          title="No agreements yet"
          description="Browse the marketplace to propose an agreement"
          action={
            <a
              href="#/buyer/marketplace"
              className="inline-flex px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 font-medium text-sm"
            >
              Browse Marketplace
            </a>
          }
        />
      ) : (
        <div className="space-y-3">
          {sorted.map((a) => (
            <Card
              key={a.id}
              onClick={() => (window.location.hash = `#/buyer/agreements/${a.id}`)}
              className="hover:border-ndai-200 transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-gray-900">
                    {a.invention_title || `Agreement ${a.id.slice(0, 8)}...`}
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-sm text-gray-500">
                      Budget: {a.budget_cap?.toFixed(2) ?? "—"}
                    </span>
                    {a.created_at && (
                      <span className="text-xs text-gray-400">{timeAgo(a.created_at)}</span>
                    )}
                  </div>
                </div>
                <StatusBadge status={a.status} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
