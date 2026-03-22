import React, { useState, useEffect } from "react";
import { getTarget } from "../../api/targets";
import type { KnownTargetDetail } from "../../api/types";
import { PlatformBadge } from "../../components/targets/PlatformBadge";

interface Props {
  targetId: string;
}

const METHOD_LABELS: Record<string, string> = {
  nitro: "AWS Nitro Enclave",
  ec2: "EC2 Sandbox",
  manual: "Manual Review",
};

export function TargetDetailPage({ targetId }: Props) {
  const [target, setTarget] = useState<KnownTargetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getTarget(targetId)
      .then(setTarget)
      .catch((e) => setError(e.detail || "Failed to load target"))
      .finally(() => setLoading(false));
  }, [targetId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  if (!target) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-danger-400 text-sm">{error || "Target not found"}</p>
      </div>
    );
  }

  return (
    <div className="animate-fade-in max-w-3xl">
      <a href="#/targets" className="text-xs text-gray-500 hover:text-gray-300 transition-colors mb-4 inline-block">
        &larr; Back to Targets
      </a>

      {/* Header */}
      <div className="glass-card p-6 mb-6">
        <div className="flex items-start gap-4">
          <span className="text-4xl leading-none">{target.icon_emoji}</span>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-white">{target.display_name}</h1>
              <PlatformBadge platform={target.platform} />
              {target.has_prebuilt && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-medium bg-success-500/15 text-success-400 border-success-500/25">
                  Ready
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 font-mono mt-1">v{target.current_version}</p>
            {target.description && (
              <p className="text-sm text-gray-400 mt-3 leading-relaxed">{target.description}</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-5 pt-5 border-t border-surface-700/50">
          <div>
            <span className="block text-[10px] text-gray-600 uppercase tracking-wider">Method</span>
            <span className="text-sm text-gray-300 font-medium">
              {METHOD_LABELS[target.verification_method] || target.verification_method}
            </span>
          </div>
          <div>
            <span className="block text-[10px] text-gray-600 uppercase tracking-wider">Escrow</span>
            <span className="text-sm text-accent-400 font-mono">${target.escrow_amount_usd}</span>
          </div>
          <div>
            <span className="block text-[10px] text-gray-600 uppercase tracking-wider">Build Status</span>
            <span className={`text-sm font-medium ${
              target.build_status === "ready" ? "text-success-400" : "text-gray-400"
            }`}>
              {target.build_status}
            </span>
          </div>
        </div>
      </div>

      {/* PoC Instructions */}
      {target.poc_instructions && (
        <div className="glass-card p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">PoC Instructions</h2>
          <div className="bg-surface-900 border border-surface-700 rounded-lg p-4">
            <pre className="text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">
              {target.poc_instructions}
            </pre>
          </div>
        </div>
      )}

      {/* Capabilities */}
      {target.supported_capabilities && target.supported_capabilities.length > 0 && (
        <div className="glass-card p-6 mb-6">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">Supported Capabilities</h2>
          <div className="flex flex-wrap gap-2">
            {target.supported_capabilities.map((cap) => (
              <span
                key={cap}
                className="px-2.5 py-1 rounded-full bg-accent-400/10 text-accent-400 text-xs font-medium border border-accent-400/20"
              >
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => (window.location.hash = `#/proposals/new?target=${target.id}`)}
        className="w-full py-3 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 transition-colors text-sm"
      >
        Submit PoC
      </button>
    </div>
  );
}
