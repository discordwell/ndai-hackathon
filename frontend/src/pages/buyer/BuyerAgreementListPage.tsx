import React from "react";
import { Card } from "../../components/shared/Card";
import { EmptyState } from "../../components/shared/EmptyState";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { useAgreements } from "../../hooks/useAgreements";

export function BuyerAgreementListPage() {
  const { agreements, loading, error } = useAgreements();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">My Agreements</h1>
      {loading ? (
        <LoadingSpinner />
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
        <div className="space-y-4">
          {agreements.map((a) => (
            <Card
              key={a.id}
              onClick={() => (window.location.hash = `#/buyer/agreements/${a.id}`)}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-gray-900">
                    Agreement {a.id.slice(0, 8)}...
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    Budget cap: {a.budget_cap?.toFixed(2) ?? "—"} | Theta:{" "}
                    {a.theta?.toFixed(3) ?? "—"}
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
