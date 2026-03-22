import React, { useState, useEffect } from "react";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";
import {
  listVulnListings,
  createVulnAgreement,
  type VulnListingResponse,
} from "../../api/vulns";

const IMPACT_COLORS: Record<string, string> = {
  RCE: "bg-red-100 text-red-800",
  LPE: "bg-orange-100 text-orange-800",
  InfoLeak: "bg-yellow-100 text-yellow-800",
  DoS: "bg-blue-100 text-blue-800",
};

export function VulnMarketplacePage() {
  const [listings, setListings] = useState<VulnListingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [budgetCap, setBudgetCap] = useState("0.5");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    listVulnListings()
      .then(setListings)
      .catch((e) => setError(e.detail || "Failed to load listings"))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreateAgreement() {
    if (!selectedId) return;
    setCreating(true);
    setCreateError("");
    try {
      const agreement = await createVulnAgreement({
        vulnerability_id: selectedId,
        budget_cap: parseFloat(budgetCap),
      });
      window.location.hash = `#/vuln/deals/${agreement.id}`;
    } catch (err: any) {
      setCreateError(err.detail || "Failed to create agreement");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Zero-Day Marketplace</h1>
        <a
          href="#/vuln/submit"
          className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium"
        >
          Submit Vulnerability
        </a>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : listings.length === 0 ? (
        <EmptyState
          title="No vulnerabilities listed"
          description="Check back later or submit your own"
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {listings.map((v) => (
              <div
                key={v.id}
                onClick={() => setSelectedId(v.id)}
                className={`bg-white rounded-xl border p-5 cursor-pointer transition-all ${
                  selectedId === v.id
                    ? "border-ndai-500 ring-2 ring-ndai-200"
                    : "border-gray-100 hover:border-gray-300"
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-semibold text-lg">
                      {v.target_software}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {v.vulnerability_class}
                    </p>
                  </div>
                  <span
                    className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${
                      IMPACT_COLORS[v.impact_type] || "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {v.impact_type}
                  </span>
                </div>
                <div className="flex gap-4 text-xs text-gray-500 mt-3">
                  <span>CVSS: {v.cvss_self_assessed.toFixed(1)}</span>
                  <span>Patch: {v.patch_status}</span>
                  <span>{v.exclusivity}</span>
                </div>
                {v.anonymized_summary && (
                  <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                    {v.anonymized_summary}
                  </p>
                )}
              </div>
            ))}
          </div>

          {selectedId && (
            <div className="bg-white rounded-xl border border-gray-100 p-6 h-fit sticky top-8">
              <h3 className="font-semibold mb-4">Initiate Deal</h3>
              <p className="text-sm text-gray-500 mb-4">
                Vuln: {selectedId.slice(0, 12)}...
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
                {creating ? "Creating..." : "Propose Deal"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
