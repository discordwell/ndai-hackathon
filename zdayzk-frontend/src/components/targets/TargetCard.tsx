import React from "react";
import type { KnownTarget } from "../../api/types";
import { PlatformBadge } from "./PlatformBadge";

const METHOD_STYLES: Record<string, string> = {
  nitro: "bg-accent-400/15 text-accent-400 border-accent-400/25",
  ec2: "bg-info-500/15 text-info-400 border-info-500/25",
  manual: "bg-surface-700 text-gray-400 border-surface-600",
};

interface Props {
  target: KnownTarget;
  onClick?: () => void;
}

export function TargetCard({ target, onClick }: Props) {
  return (
    <div
      onClick={onClick}
      className="glass-card p-5 cursor-pointer transition-all duration-200 hover:border-surface-600 flex flex-col"
    >
      <div className="flex items-start justify-between mb-3">
        <span className="text-3xl leading-none">{target.icon_emoji}</span>
        <div className="flex items-center gap-2">
          {target.has_prebuilt && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-medium bg-success-500/15 text-success-400 border-success-500/25">
              Ready
            </span>
          )}
          <PlatformBadge platform={target.platform} />
        </div>
      </div>

      <h3 className="font-semibold text-white text-sm">{target.display_name}</h3>
      <p className="text-xs text-gray-500 font-mono mt-0.5">v{target.current_version}</p>

      <div className="flex items-center gap-3 mt-3 text-[11px] text-gray-500">
        <span className="font-mono text-accent-400">${target.escrow_amount_usd} deposit</span>
        <span
          className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium ${
            METHOD_STYLES[target.verification_method] || METHOD_STYLES.manual
          }`}
        >
          {target.verification_method}
        </span>
      </div>

      <div className="mt-auto pt-4">
        <button
          onClick={(e) => {
            e.stopPropagation();
            window.location.hash = `#/proposals/new?target=${target.id}`;
          }}
          className="w-full py-2 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 transition-colors text-xs"
        >
          Submit PoC
        </button>
      </div>
    </div>
  );
}
