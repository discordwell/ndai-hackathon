import React, { useState, useEffect } from "react";
import { listMyVulns, type ZKVulnResponse } from "../../api/zkVulns";

const IMPACT_COLORS: Record<string, string> = {
  RCE: "bg-red-500/20 text-red-400 border-red-500/30",
  LPE: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  InfoLeak: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  DoS: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

function cvssColor(score: number): string {
  if (score >= 9) return "text-red-400";
  if (score >= 7) return "text-orange-400";
  if (score >= 4) return "text-yellow-400";
  return "text-green-400";
}

const STATUS_COLORS: Record<string, string> = {
  listed: "bg-green-500/20 text-green-400 border-green-500/30",
  pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  sold: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  withdrawn: "bg-void-700 text-void-400 border-void-600",
};

export function ZKMyListingsPage() {
  const [vulns, setVulns] = useState<ZKVulnResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listMyVulns()
      .then(setVulns)
      .catch((e) => setError(e.message || "Failed to load listings"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-void-50">My Listings</h1>
        <a
          href="#/zk/submit"
          className="px-3 py-1.5 bg-void-500 hover:bg-void-400 text-white rounded text-xs font-medium transition-colors"
        >
          + Submit New
        </a>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-void-400" />
        </div>
      ) : error ? (
        <div className="text-red-400 text-sm">{error}</div>
      ) : vulns.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-void-400 text-sm mb-3">
            You have not submitted any vulnerabilities yet.
          </p>
          <a
            href="#/zk/submit"
            className="px-4 py-2 bg-void-500 hover:bg-void-400 text-white rounded text-sm font-medium transition-colors"
          >
            Submit Your First
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {vulns.map((v) => (
            <div
              key={v.id}
              className="bg-void-800 border border-void-700 hover:border-void-500 rounded-lg p-4 transition-all"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-semibold text-void-50 truncate pr-2">
                  {v.target_software}
                </h3>
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded border shrink-0 ${
                    IMPACT_COLORS[v.impact_type] ||
                    "bg-void-700 text-void-300 border-void-600"
                  }`}
                >
                  {v.impact_type}
                </span>
              </div>

              <p className="text-xs text-void-400 mb-2">
                {v.vulnerability_class} &middot; {v.target_version}
              </p>

              <div className="flex items-center gap-3 text-xs mb-2">
                <span
                  className={`font-mono font-bold ${cvssColor(v.cvss_self_assessed)}`}
                >
                  {v.cvss_self_assessed.toFixed(1)}
                </span>
                <span className="text-void-200 font-medium">
                  {v.asking_price_eth} ETH
                </span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded ${
                    v.exclusivity === "exclusive"
                      ? "bg-purple-500/20 text-purple-400"
                      : "bg-void-700 text-void-400"
                  }`}
                >
                  {v.exclusivity}
                </span>
              </div>

              <div className="flex items-center justify-between mt-3 pt-3 border-t border-void-700">
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${
                    STATUS_COLORS[v.status] ||
                    "bg-void-700 text-void-300 border-void-600"
                  }`}
                >
                  {v.status}
                </span>
                <span className="text-[10px] text-void-500">
                  {new Date(v.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
