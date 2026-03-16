import React, { useState } from "react";
import { ListingCard } from "../../components/buyer/ListingCard";
import { EmptyState } from "../../components/shared/EmptyState";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { useListings } from "../../hooks/useListings";
import { createAgreement } from "../../api/agreements";

export function MarketplacePage() {
  const { listings, loading, error } = useListings();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [budgetCap, setBudgetCap] = useState("1.0");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  async function handleCreateAgreement() {
    if (!selectedId) return;
    setCreating(true);
    setCreateError("");
    try {
      const agreement = await createAgreement({
        invention_id: selectedId,
        budget_cap: parseFloat(budgetCap),
      });
      window.location.hash = `#/buyer/agreements/${agreement.id}`;
    } catch (err: any) {
      setCreateError(err.detail || "Failed to create agreement");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Marketplace</h1>
      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : listings.length === 0 ? (
        <EmptyState
          title="No inventions available"
          description="Check back later for new listings"
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {listings.map((l) => (
              <ListingCard
                key={l.id}
                listing={l}
                onSelect={setSelectedId}
              />
            ))}
          </div>
          {selectedId && (
            <div className="bg-white rounded-xl border border-gray-100 p-6 h-fit sticky top-8">
              <h3 className="font-semibold mb-4">Create Agreement</h3>
              <p className="text-sm text-gray-500 mb-4">
                Invention: {selectedId.slice(0, 12)}...
              </p>
              {createError && (
                <div className="bg-red-50 text-red-700 p-2 rounded text-sm mb-3">
                  {createError}
                </div>
              )}
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Budget Cap
              </label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={budgetCap}
                onChange={(e) => setBudgetCap(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm mb-4"
              />
              <button
                onClick={handleCreateAgreement}
                disabled={creating}
                className="w-full py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm"
              >
                {creating ? "Creating..." : "Propose Agreement"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
