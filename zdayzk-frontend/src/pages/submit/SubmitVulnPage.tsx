import React, { useState } from "react";
import { createVuln } from "../../api/vulns";
import type { VulnCreateRequest } from "../../api/types";

const IMPACT_TYPES = ["RCE", "LPE", "InfoLeak", "DoS"];
const PATCH_STATUSES = ["unpatched", "patched", "unknown"];
const EXCLUSIVITIES = ["exclusive", "non-exclusive"];
const SOFTWARE_CATEGORIES = [
  "browser", "operating_system", "server", "embedded", "mobile",
  "networking", "cloud", "database", "iot", "other",
];

export function SubmitVulnPage() {
  const [form, setForm] = useState<VulnCreateRequest>({
    target_software: "",
    target_version: "",
    vulnerability_class: "",
    impact_type: "RCE",
    affected_component: "",
    anonymized_summary: "",
    cvss_self_assessed: 7.0,
    discovery_date: new Date().toISOString().split("T")[0],
    patch_status: "unpatched",
    exclusivity: "exclusive",
    embargo_days: 90,
    outside_option_value: 0.3,
    max_disclosure_level: 2,
    software_category: "server",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function update<K extends keyof VulnCreateRequest>(key: K, value: VulnCreateRequest[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.target_software || !form.vulnerability_class) {
      setError("Target software and vulnerability class are required");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await createVuln(form);
      window.location.hash = "#/dashboard";
    } catch (err: any) {
      setError(err.detail || "Failed to submit vulnerability");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="animate-fade-in max-w-2xl">
      <h1 className="text-xl font-bold text-white mb-1">Submit Vulnerability</h1>
      <p className="text-xs text-gray-500 mb-6">
        Your submission is encrypted and anonymized before listing.
      </p>

      {error && (
        <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Target */}
        <div className="glass-card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <span className="w-5 h-5 rounded bg-accent-400/10 text-accent-400 text-[10px] font-mono flex items-center justify-center">1</span>
            Target
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Software *</label>
              <input
                value={form.target_software}
                onChange={(e) => update("target_software", e.target.value)}
                placeholder="e.g. Apache httpd"
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              />
            </div>
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Version</label>
              <input
                value={form.target_version}
                onChange={(e) => update("target_version", e.target.value)}
                placeholder="e.g. 2.4.51"
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              />
            </div>
          </div>
          <div>
            <label className="block text-[11px] text-gray-500 mb-1">Affected Component</label>
            <input
              value={form.affected_component || ""}
              onChange={(e) => update("affected_component", e.target.value)}
              placeholder="e.g. mod_proxy"
              className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
            />
          </div>
          <div>
            <label className="block text-[11px] text-gray-500 mb-1">Software Category</label>
            <select
              value={form.software_category}
              onChange={(e) => update("software_category", e.target.value)}
              className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
            >
              {SOFTWARE_CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Classification */}
        <div className="glass-card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <span className="w-5 h-5 rounded bg-accent-400/10 text-accent-400 text-[10px] font-mono flex items-center justify-center">2</span>
            Classification
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Vulnerability Class *</label>
              <input
                value={form.vulnerability_class}
                onChange={(e) => update("vulnerability_class", e.target.value)}
                placeholder="e.g. Buffer Overflow (CWE-120)"
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              />
            </div>
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Impact Type</label>
              <select
                value={form.impact_type}
                onChange={(e) => update("impact_type", e.target.value)}
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              >
                {IMPACT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[11px] text-gray-500 mb-1">
              CVSS Self-Assessed: <span className="text-accent-400 font-mono">{form.cvss_self_assessed.toFixed(1)}</span>
            </label>
            <input
              type="range"
              min={0}
              max={10}
              step={0.1}
              value={form.cvss_self_assessed}
              onChange={(e) => update("cvss_self_assessed", parseFloat(e.target.value))}
              className="w-full accent-accent-400"
            />
          </div>
          <div>
            <label className="block text-[11px] text-gray-500 mb-1">Anonymized Summary</label>
            <textarea
              value={form.anonymized_summary || ""}
              onChange={(e) => update("anonymized_summary", e.target.value)}
              rows={3}
              placeholder="Brief description visible to buyers (no identifying details)"
              className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50 resize-none"
            />
          </div>
        </div>

        {/* Terms */}
        <div className="glass-card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
            <span className="w-5 h-5 rounded bg-accent-400/10 text-accent-400 text-[10px] font-mono flex items-center justify-center">3</span>
            Terms
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Patch Status</label>
              <select
                value={form.patch_status}
                onChange={(e) => update("patch_status", e.target.value)}
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              >
                {PATCH_STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Exclusivity</label>
              <select
                value={form.exclusivity}
                onChange={(e) => update("exclusivity", e.target.value)}
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              >
                {EXCLUSIVITIES.map((e) => (
                  <option key={e} value={e}>{e}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Embargo (days)</label>
              <input
                type="number"
                min={0}
                max={365}
                value={form.embargo_days}
                onChange={(e) => update("embargo_days", parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Discovery Date</label>
              <input
                type="date"
                value={form.discovery_date}
                onChange={(e) => update("discovery_date", e.target.value)}
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              />
            </div>
            <div>
              <label className="block text-[11px] text-gray-500 mb-1">
                Outside Option: <span className="text-accent-400 font-mono">{(form.outside_option_value ?? 0.3).toFixed(2)}</span>
              </label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={form.outside_option_value ?? 0.3}
                onChange={(e) => update("outside_option_value", parseFloat(e.target.value))}
                className="w-full accent-accent-400"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-3 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 disabled:opacity-50 transition-colors text-sm"
        >
          {submitting ? "Submitting..." : "Submit Vulnerability"}
        </button>
      </form>
    </div>
  );
}
