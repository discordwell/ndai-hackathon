import React, { useState } from "react";
import { createVuln } from "../../api/zkVulns";

const VULN_CLASSES = [
  "CWE-79",
  "CWE-89",
  "CWE-94",
  "CWE-119",
  "CWE-200",
  "CWE-264",
  "CWE-352",
  "CWE-400",
];

const IMPACT_TYPES = ["RCE", "LPE", "InfoLeak", "DoS"];

const inputCls =
  "w-full px-3 py-2 bg-void-900 border border-void-600 text-void-50 rounded text-sm focus:border-void-400 focus:outline-none placeholder:text-void-500";
const labelCls = "block text-xs font-medium text-void-200 mb-1";

export function ZKSubmitPage() {
  const [form, setForm] = useState({
    target_software: "",
    target_version: "",
    vulnerability_class: "CWE-79",
    impact_type: "RCE",
    affected_component: "",
    anonymized_summary: "",
    cvss_self_assessed: 7.0,
    asking_price_eth: 1.0,
    discovery_date: new Date().toISOString().slice(0, 10),
    patch_status: "unpatched",
    exclusivity: "exclusive",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function update(field: string, value: any) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await createVuln(form);
      window.location.hash = "#/zk/mine";
    } catch (err: any) {
      setError(err.message || "Failed to submit vulnerability");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-void-50 mb-4">
        Submit Vulnerability
      </h1>

      {error && (
        <div className="text-xs text-red-400 bg-red-900/30 border border-red-800 rounded px-3 py-2 mb-4">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-void-800 border border-void-700 rounded-lg p-5 space-y-4"
      >
        {/* Row: Target Software + Version */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Target Software</label>
            <input
              type="text"
              required
              value={form.target_software}
              onChange={(e) => update("target_software", e.target.value)}
              placeholder="e.g., Apache httpd"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Version</label>
            <input
              type="text"
              required
              value={form.target_version}
              onChange={(e) => update("target_version", e.target.value)}
              placeholder="e.g., 2.4.x"
              className={inputCls}
            />
          </div>
        </div>

        {/* Row: CWE Class + Impact Type */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Vulnerability Class</label>
            <select
              value={form.vulnerability_class}
              onChange={(e) => update("vulnerability_class", e.target.value)}
              className={inputCls}
            >
              {VULN_CLASSES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Impact Type</label>
            <select
              value={form.impact_type}
              onChange={(e) => update("impact_type", e.target.value)}
              className={inputCls}
            >
              {IMPACT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Affected Component */}
        <div>
          <label className={labelCls}>Affected Component (optional)</label>
          <input
            type="text"
            value={form.affected_component}
            onChange={(e) => update("affected_component", e.target.value)}
            placeholder="e.g., mod_proxy"
            className={inputCls}
          />
        </div>

        {/* Summary */}
        <div>
          <label className={labelCls}>
            Anonymized Summary (visible to buyers)
          </label>
          <textarea
            rows={3}
            value={form.anonymized_summary}
            onChange={(e) => update("anonymized_summary", e.target.value)}
            placeholder="Brief description visible in marketplace listings..."
            className={inputCls + " resize-none"}
          />
        </div>

        {/* Row: CVSS + Price + Discovery Date */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className={labelCls}>CVSS Score</label>
            <input
              type="number"
              min="0"
              max="10"
              step="0.1"
              value={form.cvss_self_assessed}
              onChange={(e) =>
                update("cvss_self_assessed", parseFloat(e.target.value))
              }
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Asking Price (ETH)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.asking_price_eth}
              onChange={(e) =>
                update("asking_price_eth", parseFloat(e.target.value))
              }
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Discovery Date</label>
            <input
              type="date"
              value={form.discovery_date}
              onChange={(e) => update("discovery_date", e.target.value)}
              className={inputCls}
            />
          </div>
        </div>

        {/* Row: Patch Status + Exclusivity */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Patch Status</label>
            <select
              value={form.patch_status}
              onChange={(e) => update("patch_status", e.target.value)}
              className={inputCls}
            >
              <option value="unpatched">Unpatched</option>
              <option value="patched">Patched</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>Exclusivity</label>
            <select
              value={form.exclusivity}
              onChange={(e) => update("exclusivity", e.target.value)}
              className={inputCls}
            >
              <option value="exclusive">Exclusive</option>
              <option value="non-exclusive">Non-exclusive</option>
            </select>
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 bg-void-500 hover:bg-void-400 text-white rounded font-medium text-sm disabled:opacity-50 transition-colors"
        >
          {submitting ? "Submitting..." : "Submit Vulnerability"}
        </button>
      </form>
    </div>
  );
}
