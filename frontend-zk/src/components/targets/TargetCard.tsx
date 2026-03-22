import React from "react";
import type { KnownTarget } from "../../api/types";
import { PlatformBadge } from "./PlatformBadge";

const METHOD_STYLES: Record<string, string> = {
  nitro: "bg-zk-accent/15 text-zk-accent border-zk-accent/25",
  ec2: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  manual: "bg-zk-muted/15 text-zk-muted border-zk-muted/25",
};

interface Props {
  target: KnownTarget;
  onClick?: () => void;
}

export function TargetCard({ target, onClick }: Props) {
  return (
    <div
      onClick={onClick}
      className="border-3 border-zk-border bg-white p-5 cursor-pointer transition-all duration-200 hover:border-zk-text flex flex-col"
    >
      <div className="flex items-start justify-between mb-3">
        <span className="text-3xl leading-none">{target.icon_emoji}</span>
        <div className="flex items-center gap-2">
          {target.has_prebuilt && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 border-2 border-emerald-600 text-[10px] font-mono font-bold text-emerald-700 uppercase">
              Ready
            </span>
          )}
          <PlatformBadge platform={target.platform} />
        </div>
      </div>

      <h3 className="font-mono font-bold text-zk-text text-sm">{target.display_name}</h3>
      <p className="text-xs text-zk-muted font-mono mt-0.5">v{target.current_version}</p>

      <div className="flex items-center gap-3 mt-3 text-[11px] text-zk-muted">
        <span className="font-mono font-bold text-zk-accent">${target.escrow_amount_usd} deposit</span>
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
          className="w-full py-2 bg-zk-text text-white font-mono font-bold text-xs uppercase tracking-wider hover:bg-zk-accent transition-colors"
        >
          Submit PoC
        </button>
      </div>
    </div>
  );
}
