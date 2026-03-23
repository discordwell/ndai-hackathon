import React, { useState, useEffect } from "react";
import { listMyVulns, type ZKVulnResponse } from "../../api/zkVulns";
import { createAuction } from "../../api/zkAuctions";

const inputCls =
  "w-full px-3 py-2 bg-void-900 border border-void-600 text-void-50 rounded text-sm focus:border-void-400 focus:outline-none placeholder:text-void-500";
const labelCls = "block text-xs font-medium text-void-200 mb-1";

const DURATIONS = [
  { label: "1 hour", value: 1 },
  { label: "6 hours", value: 6 },
  { label: "12 hours", value: 12 },
  { label: "24 hours", value: 24 },
  { label: "48 hours", value: 48 },
  { label: "72 hours", value: 72 },
  { label: "7 days", value: 168 },
];

export function ZKAuctionCreatePage() {
  const [vulns, setVulns] = useState<ZKVulnResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    vulnerability_id: "",
    reserve_price_eth: 1.0,
    duration_hours: 24,
    serious_customers_only: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listMyVulns()
      .then((v) => setVulns(v.filter((x) => x.status === "active")))
      .catch(() => setError("Failed to load your listings"))
      .finally(() => setLoading(false));
  }, []);

  function update(field: string, value: any) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.vulnerability_id) {
      setError("Select a vulnerability");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const auction = await createAuction(form);
      window.location.hash = `#/zk/auctions/${auction.id}`;
    } catch (err: any) {
      setError(err.message || "Failed to create auction");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-void-400" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-void-50 mb-4">Create Auction</h1>

      {error && (
        <div className="text-xs text-red-400 bg-red-900/30 border border-red-800 rounded px-3 py-2 mb-4">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-void-800 border border-void-700 rounded-lg p-5 space-y-4"
      >
        {/* Select vulnerability */}
        <div>
          <label className={labelCls}>Vulnerability</label>
          {vulns.length === 0 ? (
            <p className="text-xs text-void-400">
              No active listings. <a href="#/zk/submit" className="text-void-200 underline">Submit one first.</a>
            </p>
          ) : (
            <select
              value={form.vulnerability_id}
              onChange={(e) => update("vulnerability_id", e.target.value)}
              className={inputCls}
            >
              <option value="">Select a listing...</option>
              {vulns.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.target_software} ({v.impact_type}) — {v.asking_price_eth} ETH
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Reserve price + duration */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Reserve Price (ETH)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.reserve_price_eth}
              onChange={(e) => update("reserve_price_eth", parseFloat(e.target.value))}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Duration</label>
            <select
              value={form.duration_hours}
              onChange={(e) => update("duration_hours", parseInt(e.target.value))}
              className={inputCls}
            >
              {DURATIONS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* SC-only toggle */}
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="sc-only"
            checked={form.serious_customers_only}
            onChange={(e) => update("serious_customers_only", e.target.checked)}
            className="w-4 h-4 rounded border-void-600 bg-void-900 text-void-400 focus:ring-void-500"
          />
          <label htmlFor="sc-only" className="text-xs text-void-200">
            Restrict to Serious Customers only ($5K deposit required to bid)
          </label>
        </div>

        <button
          type="submit"
          disabled={submitting || vulns.length === 0}
          className="w-full py-2.5 bg-void-500 hover:bg-void-400 text-white rounded font-medium text-sm disabled:opacity-50 transition-colors"
        >
          {submitting ? "Creating..." : "Create Auction"}
        </button>
      </form>
    </div>
  );
}
