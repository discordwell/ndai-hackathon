import React, { useState } from "react";
import { createVuln } from "../../api/vulns";

const IMPACT_TYPES = ["RCE", "LPE", "InfoLeak", "DoS"];
const SOFTWARE_CATEGORIES = [
  "browser", "os_kernel", "web_server", "enterprise", "embedded", "mobile", "default",
];

export function VulnSubmitPage() {
  const [form, setForm] = useState({
    target_software: "",
    target_version: "",
    vulnerability_class: "",
    impact_type: "RCE",
    affected_component: "",
    anonymized_summary: "",
    cvss_self_assessed: 7.0,
    discovery_date: new Date().toISOString().slice(0, 10),
    patch_status: "unpatched",
    exclusivity: "exclusive",
    embargo_days: 90,
    outside_option_value: 0.3,
    max_disclosure_level: 3,
    software_category: "default",
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
      window.location.hash = "#/vuln/mine";
    } catch (err: any) {
      setError(err.detail || "Failed to submit vulnerability");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Submit Vulnerability</h1>
      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4 text-sm">
          {error}
        </div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Software</label>
            <input
              type="text" required value={form.target_software}
              onChange={(e) => update("target_software", e.target.value)}
              placeholder="e.g., Apache httpd"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Version</label>
            <input
              type="text" required value={form.target_version}
              onChange={(e) => update("target_version", e.target.value)}
              placeholder="e.g., 2.4.x"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">CWE Class</label>
            <input
              type="text" required value={form.vulnerability_class}
              onChange={(e) => update("vulnerability_class", e.target.value)}
              placeholder="e.g., CWE-787"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Impact Type</label>
            <select
              value={form.impact_type}
              onChange={(e) => update("impact_type", e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            >
              {IMPACT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Affected Component</label>
          <input
            type="text" value={form.affected_component}
            onChange={(e) => update("affected_component", e.target.value)}
            placeholder="e.g., mod_proxy"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Summary (anonymized, visible to buyers)</label>
          <textarea
            rows={3} value={form.anonymized_summary}
            onChange={(e) => update("anonymized_summary", e.target.value)}
            placeholder="Brief description visible in marketplace listings..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
          />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">CVSS Score</label>
            <input
              type="number" min="0" max="10" step="0.1" value={form.cvss_self_assessed}
              onChange={(e) => update("cvss_self_assessed", parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Discovery Date</label>
            <input
              type="date" value={form.discovery_date}
              onChange={(e) => update("discovery_date", e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Software Category</label>
            <select
              value={form.software_category}
              onChange={(e) => update("software_category", e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            >
              {SOFTWARE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Exclusivity</label>
            <select
              value={form.exclusivity}
              onChange={(e) => update("exclusivity", e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            >
              <option value="exclusive">Exclusive</option>
              <option value="non-exclusive">Non-exclusive</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Embargo (days)</label>
            <input
              type="number" min="0" max="365" value={form.embargo_days}
              onChange={(e) => update("embargo_days", parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Disclosure Level</label>
            <select
              value={form.max_disclosure_level}
              onChange={(e) => update("max_disclosure_level", parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
            >
              <option value={0}>0 - Class + Impact only</option>
              <option value={1}>1 - + Component</option>
              <option value={2}>2 - + Triggers</option>
              <option value={3}>3 - + PoC Summary</option>
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium"
        >
          {submitting ? "Submitting..." : "Submit Vulnerability"}
        </button>
      </form>
    </div>
  );
}
