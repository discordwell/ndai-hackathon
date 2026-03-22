import React, { useState, useEffect, useMemo } from "react";
import { listVulnListings } from "../../api/vulns";
import type { VulnListingResponse } from "../../api/types";
import { ListingCard } from "../../components/marketplace/ListingCard";
import { FilterBar, type Filters } from "../../components/marketplace/FilterBar";

export function MarketplacePage() {
  const [listings, setListings] = useState<VulnListingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<Filters>({ impactType: "", minCvss: 0, exclusivity: "" });

  useEffect(() => {
    listVulnListings()
      .then(setListings)
      .catch((e) => setError(e.detail || "Failed to load listings"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    return listings.filter((l) => {
      if (filters.impactType && l.impact_type !== filters.impactType) return false;
      if (l.cvss_self_assessed < filters.minCvss) return false;
      if (filters.exclusivity && l.exclusivity !== filters.exclusivity) return false;
      return true;
    });
  }, [listings, filters]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Marketplace</h1>
          <p className="text-xs text-gray-500 mt-1">
            {filtered.length} {filtered.length === 1 ? "listing" : "listings"}
          </p>
        </div>
        <a
          href="#/submit"
          className="px-4 py-2 bg-accent-400 text-surface-950 font-medium rounded-lg hover:bg-accent-300 transition-colors text-xs"
        >
          Submit Vulnerability
        </a>
      </div>

      {error && (
        <div className="glass-card p-4 border-danger-500/30 text-danger-400 text-sm mb-6">
          {error}
        </div>
      )}

      <FilterBar filters={filters} onChange={setFilters} />

      {filtered.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-gray-400 text-sm">No vulnerabilities match your filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((listing) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              onClick={() => (window.location.hash = `#/marketplace/${listing.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
