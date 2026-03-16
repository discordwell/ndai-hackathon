import React from "react";
import { InventionCard } from "../../components/seller/InventionCard";
import { EmptyState } from "../../components/shared/EmptyState";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { useInventions } from "../../hooks/useInventions";

export function InventionListPage() {
  const { inventions, loading, error } = useInventions();

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">My Inventions</h1>
        <a
          href="#/seller/inventions/new"
          className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 font-medium text-sm"
        >
          New Invention
        </a>
      </div>
      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : inventions.length === 0 ? (
        <EmptyState
          title="No inventions yet"
          description="Submit your first invention to get started"
          action={
            <a
              href="#/seller/inventions/new"
              className="inline-flex px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 font-medium text-sm"
            >
              Submit Invention
            </a>
          }
        />
      ) : (
        <div className="space-y-4">
          {inventions.map((inv) => (
            <InventionCard key={inv.id} invention={inv} />
          ))}
        </div>
      )}
    </div>
  );
}
