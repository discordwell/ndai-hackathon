import React, { useState, useMemo } from "react";
import { ListingCard } from "../../components/buyer/ListingCard";
import { EmptyState } from "../../components/shared/EmptyState";
import { ListSkeleton } from "../../components/shared/Skeleton";
import { useListings } from "../../hooks/useListings";
import { createAgreement } from "../../api/agreements";

const STAGES = ["concept", "prototype", "tested", "production"];

export function MarketplacePage() {
  const { listings, loading, error } = useListings();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [budgetCap, setBudgetCap] = useState("1.0");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<string | null>(null);

  const categories = useMemo(
    () => [...new Set(listings.map((l) => l.category).filter(Boolean))].sort() as string[],
    [listings]
  );

  const filtered = useMemo(() => {
    let result = listings;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (l) =>
          l.title.toLowerCase().includes(q) ||
          (l.anonymized_summary || "").toLowerCase().includes(q)
      );
    }
    if (categoryFilter) {
      result = result.filter((l) => l.category === categoryFilter);
    }
    if (stageFilter) {
      result = result.filter((l) => l.development_stage === stageFilter);
    }
    return result;
  }, [listings, search, categoryFilter, stageFilter]);

  const selectedListing = listings.find((l) => l.id === selectedId);

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
    <div className="animate-fadeIn">
      <h1 className="text-2xl font-bold mb-6">Marketplace</h1>

      {loading ? (
        <ListSkeleton />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : listings.length === 0 ? (
        <EmptyState
          title="No inventions available"
          description="Check back later for new listings"
        />
      ) : (
        <>
          {/* Search & Filters */}
          <div className="mb-6 space-y-3">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search inventions..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {/* Category filters */}
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    categoryFilter === cat
                      ? "bg-ndai-600 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {cat}
                </button>
              ))}
              {categories.length > 0 && <div className="w-px bg-gray-200 mx-1" />}
              {/* Stage filters */}
              {STAGES.map((stage) => (
                <button
                  key={stage}
                  onClick={() => setStageFilter(stageFilter === stage ? null : stage)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize ${
                    stageFilter === stage
                      ? "bg-ndai-600 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {stage}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {filtered.length === 0 ? (
                <div className="text-sm text-gray-500 py-8 text-center">
                  No inventions match your filters
                </div>
              ) : (
                filtered.map((l) => (
                  <ListingCard
                    key={l.id}
                    listing={l}
                    selected={l.id === selectedId}
                    onSelect={setSelectedId}
                  />
                ))
              )}
            </div>
            {selectedId && selectedListing && (
              <div className="bg-white rounded-xl border border-gray-100 p-6 h-fit sticky top-8 animate-scaleIn">
                <h3 className="font-semibold mb-2">Create Agreement</h3>
                <p className="text-sm text-gray-700 mb-1">{selectedListing.title}</p>
                <p className="text-xs text-gray-400 mb-4 capitalize">
                  {selectedListing.development_stage}
                  {selectedListing.category ? ` · ${selectedListing.category}` : ""}
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
                  className="w-full py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm transition-colors"
                >
                  {creating ? "Creating..." : "Propose Agreement"}
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
