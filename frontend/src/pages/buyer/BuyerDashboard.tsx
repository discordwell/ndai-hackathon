import React from "react";
import { Card } from "../../components/shared/Card";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { DashboardSkeleton } from "../../components/shared/Skeleton";
import { useAgreements } from "../../hooks/useAgreements";
import { useListings } from "../../hooks/useListings";

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

export function BuyerDashboard() {
  const { listings, loading: listLoading } = useListings();
  const { agreements, loading: agrLoading } = useAgreements();

  if (listLoading || agrLoading) return <DashboardSkeleton />;

  const completedDeals = agreements.filter((a) =>
    a.status.startsWith("completed_agreement")
  );
  const pendingActions = agreements.filter(
    (a) => a.status === "proposed" || a.status === "confirmed"
  );
  const recentAgreements = [...agreements]
    .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))
    .slice(0, 5);

  return (
    <div className="animate-fadeIn">
      <h1 className="text-2xl font-bold mb-6">Investor Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <div className="text-3xl font-bold text-ndai-600">
            {listings.length}
          </div>
          <div className="text-sm text-gray-500 mt-1">Available Inventions</div>
          <div className="text-xs text-gray-400 mt-2">
            Browse the marketplace
          </div>
        </Card>
        <Card>
          <div className="text-3xl font-bold text-ndai-600">
            {agreements.length}
          </div>
          <div className="text-sm text-gray-500 mt-1">My Agreements</div>
          {pendingActions.length > 0 && (
            <div className="text-xs text-amber-600 mt-2">
              {pendingActions.length} need your attention
            </div>
          )}
        </Card>
        <Card>
          <div className="text-3xl font-bold text-green-600">
            {completedDeals.length}
          </div>
          <div className="text-sm text-gray-500 mt-1">Successful Deals</div>
        </Card>
      </div>

      {/* Pending Actions */}
      {pendingActions.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <span className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
            Pending Actions
          </h2>
          <div className="space-y-2">
            {pendingActions.map((a) => (
              <Card
                key={a.id}
                onClick={() => (window.location.hash = `#/buyer/agreements/${a.id}`)}
                className="hover:border-amber-200 border-amber-100 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-gray-700">
                      Agreement <span className="font-mono text-xs">{a.id.slice(0, 8)}</span>
                    </div>
                    <div className="text-xs text-amber-600 mt-0.5">
                      {a.status === "proposed" ? "Set parameters & confirm delegation" : "Ready to start negotiation"}
                    </div>
                  </div>
                  <StatusBadge status={a.status} />
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Onboarding — shown when no agreements */}
      {agreements.length === 0 && (
        <Card className="mb-8 border-ndai-100 bg-ndai-50/50">
          <h3 className="font-semibold text-ndai-800 mb-4">How NDAI Works for Investors</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-ndai-100 text-ndai-700 flex items-center justify-center text-sm font-bold flex-shrink-0">1</div>
              <div>
                <div className="font-medium text-sm text-gray-800">Browse Marketplace</div>
                <div className="text-xs text-gray-500 mt-0.5">View anonymized invention listings</div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-ndai-100 text-ndai-700 flex items-center justify-center text-sm font-bold flex-shrink-0">2</div>
              <div>
                <div className="font-medium text-sm text-gray-800">Set Your Budget</div>
                <div className="text-xs text-gray-500 mt-0.5">Define your budget cap and parameters</div>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-ndai-100 text-ndai-700 flex items-center justify-center text-sm font-bold flex-shrink-0">3</div>
              <div>
                <div className="font-medium text-sm text-gray-800">AI Agents Negotiate</div>
                <div className="text-xs text-gray-500 mt-0.5">Fair bilateral Nash bargaining in a TEE</div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Recent Activity */}
      {recentAgreements.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-3">Recent Activity</h2>
          <div className="space-y-2">
            {recentAgreements.map((a) => (
              <Card
                key={a.id}
                onClick={() => (window.location.hash = `#/buyer/agreements/${a.id}`)}
                className="hover:border-ndai-200 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-sm text-gray-700">
                      Agreement <span className="font-mono text-xs">{a.id.slice(0, 8)}</span>
                    </div>
                    {a.created_at && (
                      <span className="text-xs text-gray-400">{timeAgo(a.created_at)}</span>
                    )}
                  </div>
                  <StatusBadge status={a.status} />
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-4">
        <a
          href="#/buyer/marketplace"
          className="inline-flex px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 font-medium text-sm transition-colors"
        >
          Browse Marketplace
        </a>
        <a
          href="#/buyer/agreements"
          className="inline-flex px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm transition-colors"
        >
          View Agreements
        </a>
      </div>
    </div>
  );
}
