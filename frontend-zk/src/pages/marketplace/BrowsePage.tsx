import React, { useState, useEffect } from "react";
import { listVulnListings, type VulnListingResponse } from "../../api/vulns";
import { listRFPListings, type RFPListingResponse } from "../../api/rfps";
import { StatusBadge } from "../../components/StatusBadge";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { EmptyState } from "../../components/EmptyState";

type Tab = "all" | "vulns" | "rfps";

const IMPACT_LABEL: Record<string, string> = {
  RCE: "RCE",
  LPE: "LPE",
  InfoLeak: "LEAK",
  DoS: "DOS",
};

export function BrowsePage() {
  const [tab, setTab] = useState<Tab>("all");
  const [vulns, setVulns] = useState<VulnListingResponse[]>([]);
  const [rfps, setRFPs] = useState<RFPListingResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listVulnListings(), listRFPListings()])
      .then(([v, r]) => { setVulns(v); setRFPs(r); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  const showVulns = tab === "all" || tab === "vulns";
  const showRFPs = tab === "all" || tab === "rfps";

  return (
    <div>
      {/* Header */}
      <div className="flex items-end justify-between mb-6">
        <h1 className="font-mono text-headline">MARKETPLACE</h1>
        <div className="flex gap-1">
          <a href="#/sell/new" className="zk-btn-sm no-underline">+ VULNERABILITY</a>
          <a href="#/buy/new" className="zk-btn-sm no-underline bg-zk-accent text-white border-zk-accent hover:bg-zk-border hover:border-zk-border">+ RFP</a>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b-3 border-zk-border mb-6">
        {(["all", "vulns", "rfps"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider border-b-3 -mb-[3px]
              ${tab === t
                ? "border-zk-accent text-zk-accent"
                : "border-transparent text-zk-muted hover:text-zk-text"
              }`}
          >
            {t === "all" ? `ALL (${vulns.length + rfps.length})` :
             t === "vulns" ? `VULNERABILITIES (${vulns.length})` :
             `RFPS (${rfps.length})`}
          </button>
        ))}
      </div>

      {/* Listings */}
      <div className="space-y-0">
        {showVulns && vulns.map((v) => (
          <a
            key={`v-${v.id}`}
            href={`#/browse/vuln/${v.id}`}
            className="block border-2 border-zk-border border-b-0 last:border-b-2 p-4
                       hover:bg-white no-underline text-zk-text transition-colors"
          >
            <div className="flex items-center gap-4">
              <span className="zk-tag-danger text-[10px]">VULN</span>
              <span className="font-mono text-sm font-bold flex-1 truncate">
                {v.target_software}
              </span>
              <span className="font-mono text-xs text-zk-muted">{v.vulnerability_class}</span>
              <span className={`zk-tag text-[10px] ${
                v.impact_type === "RCE" ? "border-zk-danger text-zk-danger" :
                v.impact_type === "LPE" ? "border-zk-warn text-zk-warn" :
                "border-zk-border"
              }`}>
                {IMPACT_LABEL[v.impact_type] || v.impact_type}
              </span>
              <span className="font-mono text-sm font-bold w-12 text-right">
                {v.cvss_self_assessed.toFixed(1)}
              </span>
              <span className="font-mono text-xs text-zk-muted w-20 text-right">
                {v.exclusivity}
              </span>
            </div>
            {v.anonymized_summary && (
              <p className="text-xs text-zk-muted mt-2 ml-[72px] line-clamp-1">
                {v.anonymized_summary}
              </p>
            )}
          </a>
        ))}

        {showRFPs && rfps.map((r) => (
          <a
            key={`r-${r.id}`}
            href={`#/browse/rfp/${r.id}`}
            className="block border-2 border-zk-border border-b-0 last:border-b-2 p-4
                       hover:bg-white no-underline text-zk-text transition-colors"
          >
            <div className="flex items-center gap-4">
              <span className="zk-tag text-[10px] border-zk-link text-zk-link">RFP</span>
              <span className="font-mono text-sm font-bold flex-1 truncate">
                {r.title}
              </span>
              <span className="font-mono text-xs text-zk-muted">{r.target_software}</span>
              <span className={`zk-tag text-[10px] ${
                r.desired_capability === "RCE" ? "border-zk-danger text-zk-danger" :
                r.desired_capability === "LPE" ? "border-zk-warn text-zk-warn" :
                "border-zk-border"
              }`}>
                {IMPACT_LABEL[r.desired_capability] || r.desired_capability}
              </span>
              <span className="font-mono text-sm font-bold">
                {r.budget_min_eth}-{r.budget_max_eth} ETH
              </span>
              {r.has_patches && (
                <span className="zk-tag text-[10px] border-zk-success text-zk-success">PATCHES</span>
              )}
            </div>
          </a>
        ))}

        {!loading && vulns.length === 0 && rfps.length === 0 && (
          <EmptyState message="No listings yet" />
        )}
      </div>
    </div>
  );
}
