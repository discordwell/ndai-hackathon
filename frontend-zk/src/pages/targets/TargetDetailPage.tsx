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
        <div className="w-6 h-6 border-3 border-zk-border border-t-zk-text animate-spin" />
      </div>
    );
  }

  if (!target) {
    return (
      <div className="border-3 border-zk-border bg-white p-6 text-center">
        <p className="text-red-600 text-sm font-mono">{error || "Target not found"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <a href="#/targets" className="text-xs text-zk-muted hover:text-zk-text font-mono transition-colors mb-4 inline-block">
        &larr; BACK TO TARGETS
      </a>

      {/* Header */}
      <div className="border-3 border-zk-border bg-white p-6 mb-4">
        <div className="flex items-start gap-4">
          <span className="text-4xl leading-none">{target.icon_emoji}</span>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-mono font-extrabold text-zk-text">{target.display_name}</h1>
              <PlatformBadge platform={target.platform} />
              {target.has_prebuilt && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 border-2 border-emerald-600 text-[10px] font-mono font-bold text-emerald-700 uppercase">
                  Ready
                </span>
              )}
            </div>
            <p className="text-xs text-zk-muted font-mono mt-1">v{target.current_version}</p>
            {target.description && (
              <p className="text-sm text-zk-text mt-3 leading-relaxed font-mono">{target.description}</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-5 pt-5 border-t-2 border-zk-border">
          <div>
            <span className="block text-[10px] text-zk-dim font-mono uppercase tracking-wider">Method</span>
            <span className="text-sm text-zk-text font-mono font-bold">
              {METHOD_LABELS[target.verification_method] || target.verification_method}
            </span>
          </div>
          <div>
            <span className="block text-[10px] text-zk-dim font-mono uppercase tracking-wider">Escrow</span>
            <span className="text-sm text-zk-accent font-mono font-bold">${target.escrow_amount_usd}</span>
          </div>
          <div>
            <span className="block text-[10px] text-zk-dim font-mono uppercase tracking-wider">Build Status</span>
            <span className={`text-sm font-mono font-bold ${
              target.build_status === "ready" ? "text-emerald-700" : "text-zk-muted"
            }`}>
              {target.build_status}
            </span>
          </div>
        </div>
      </div>

      {/* Build Spec — exact environment the PoC runs against */}
      <div className="border-3 border-zk-border bg-white p-6 mb-4">
        <h2 className="text-sm font-mono font-bold text-zk-text uppercase mb-1 flex items-center gap-3">
          Build Spec
          <span className="font-mono text-label px-2 py-0.5 border-2 border-zk-accent text-zk-accent">EXACT ENVIRONMENT</span>
        </h2>
        <p className="text-xs text-zk-muted font-mono mb-4">
          This is the precise system your PoC will execute against inside the enclave.
        </p>

        <div className="space-y-3">
          {/* Base image */}
          {target.base_image && (
            <div className="flex items-baseline gap-2">
              <span className="text-[10px] text-zk-dim font-mono uppercase w-24 shrink-0">BASE</span>
              <code className="text-xs text-zk-text font-mono bg-zk-bg px-2 py-0.5 border border-zk-border">{target.base_image}</code>
            </div>
          )}

          {/* Service user */}
          <div className="flex items-baseline gap-2">
            <span className="text-[10px] text-zk-dim font-mono uppercase w-24 shrink-0">POC RUNS AS</span>
            <code className="text-xs text-zk-text font-mono bg-zk-bg px-2 py-0.5 border border-zk-border">{target.service_user}</code>
          </div>

          {/* Packages */}
          {target.packages_json && target.packages_json.length > 0 && (
            <div>
              <span className="text-[10px] text-zk-dim font-mono uppercase block mb-1">PACKAGES</span>
              <div className="bg-zk-bg border-2 border-zk-border p-3 space-y-1">
                {target.packages_json.map((pkg, i) => (
                  <div key={i} className="flex items-baseline gap-2 text-xs font-mono">
                    <span className="text-zk-text font-bold">{pkg.name}</span>
                    <span className="text-zk-muted">=</span>
                    <span className="text-zk-accent">{pkg.version}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Services */}
          {target.services_json && target.services_json.length > 0 && (
            <div>
              <span className="text-[10px] text-zk-dim font-mono uppercase block mb-1">SERVICES</span>
              <div className="bg-zk-bg border-2 border-zk-border p-3 space-y-3">
                {target.services_json.map((svc, i) => (
                  <div key={i} className="space-y-1">
                    <div className="text-xs font-mono font-bold text-zk-text">{svc.name}</div>
                    <div className="text-[11px] font-mono text-zk-muted pl-3">
                      <div><span className="text-zk-dim">$</span> {svc.start_command}</div>
                      <div className="text-zk-dim">health: {svc.health_check}</div>
                      <div className="text-zk-dim">timeout: {svc.timeout_sec}s</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Build steps */}
          {target.build_steps_json && target.build_steps_json.length > 0 && (
            <div>
              <span className="text-[10px] text-zk-dim font-mono uppercase block mb-1">BUILD STEPS</span>
              <div className="bg-zk-bg border-2 border-zk-border p-3">
                {target.build_steps_json.map((step, i) => (
                  <div key={i} className="text-[11px] font-mono text-zk-text">
                    <span className="text-zk-dim">RUN</span> {step}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Config files */}
          {target.config_files_json && target.config_files_json.length > 0 && (
            <div>
              <span className="text-[10px] text-zk-dim font-mono uppercase block mb-1">CONFIG FILES</span>
              <div className="bg-zk-bg border-2 border-zk-border p-3 space-y-1">
                {target.config_files_json.map((f, i) => (
                  <div key={i} className="text-[11px] font-mono text-zk-text">
                    <span className="text-zk-dim">COPY</span> {f.path} <span className="text-zk-dim">{f.mode ? `(${f.mode})` : ""}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* PoC Instructions */}
      {target.poc_instructions && (
        <div className="border-3 border-zk-border bg-white p-6 mb-4">
          <h2 className="text-sm font-mono font-bold text-zk-text uppercase mb-3">PoC Instructions</h2>
          <div className="bg-zk-bg border-2 border-zk-border p-4">
            <pre className="text-xs text-zk-text whitespace-pre-wrap font-mono leading-relaxed">
              {target.poc_instructions}
            </pre>
          </div>
        </div>
      )}

      {/* Capabilities */}
      {target.supported_capabilities && target.supported_capabilities.length > 0 && (
        <div className="border-3 border-zk-border bg-white p-6 mb-4">
          <h2 className="text-sm font-mono font-bold text-zk-text uppercase mb-3">Supported Capabilities</h2>
          <div className="flex flex-wrap gap-2">
            {target.supported_capabilities.map((cap) => (
              <span
                key={cap}
                className="px-2.5 py-1 border-2 border-zk-accent text-zk-accent text-xs font-mono font-bold uppercase"
              >
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => (window.location.hash = `#/proposals/new?target=${target.id}`)}
        className="w-full py-3 bg-zk-text text-white font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-accent transition-colors"
      >
        Submit PoC
      </button>
    </div>
  );
}
