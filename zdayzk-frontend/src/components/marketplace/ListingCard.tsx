import React from "react";
import type { VulnListingResponse } from "../../api/types";
import { SeverityMeter } from "./SeverityMeter";

const IMPACT_STYLES: Record<string, string> = {
  RCE: "bg-danger-500/20 text-danger-400 border-danger-500/30",
  LPE: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  InfoLeak: "bg-accent-400/20 text-accent-400 border-accent-400/30",
  DoS: "bg-info-500/20 text-info-400 border-info-500/30",
};

interface Props {
  listing: VulnListingResponse;
  selected?: boolean;
  onClick?: () => void;
}

export function ListingCard({ listing, selected, onClick }: Props) {
  return (
    <div
      onClick={onClick}
      className={`glass-card p-5 cursor-pointer transition-all duration-200 ${
        selected
          ? "border-accent-400/50 shadow-lg shadow-accent-400/5"
          : "hover:border-surface-600"
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-white text-sm">
            {listing.target_software}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5 font-mono">
            {listing.vulnerability_class}
          </p>
        </div>
        <span
          className={`text-[10px] font-medium px-2 py-0.5 rounded border ${
            IMPACT_STYLES[listing.impact_type] || "bg-surface-700 text-gray-400 border-surface-600"
          }`}
        >
          {listing.impact_type}
        </span>
      </div>

      <SeverityMeter cvss={listing.cvss_self_assessed} />

      <div className="flex items-center gap-3 mt-3 text-[11px] text-gray-500">
        <span className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${
            listing.patch_status === "unpatched" ? "bg-danger-400" : "bg-success-400"
          }`} />
          {listing.patch_status}
        </span>
        <span>{listing.exclusivity}</span>
      </div>

      {listing.anonymized_summary && (
        <p className="text-xs text-gray-400 mt-3 line-clamp-2 leading-relaxed">
          {listing.anonymized_summary}
        </p>
      )}
    </div>
  );
}
