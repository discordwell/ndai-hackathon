import React, { useState } from "react";
import { createBounty } from "../../api/bounties";

const IMPACT_TYPES = ["RCE", "LPE", "InfoLeak", "DoS"];
const VULN_CLASSES = [
  "",
  "CWE-79",
  "CWE-89",
  "CWE-94",
  "CWE-119",
  "CWE-200",
  "CWE-264",
  "CWE-352",
  "CWE-400",
];

const inputCls =
  "w-full px-3 py-2 bg-void-900 border border-void-600 text-void-50 rounded text-sm focus:border-void-400 focus:outline-none placeholder:text-void-500";
const labelCls = "block text-xs font-medium text-void-200 mb-1";

export function ZKBountyCreatePage() {
  const [form, setForm] = useState({
    target_software: "",
    target_version_constraint: "",
    desired_impact: "RCE",
    desired_vulnerability_class: "",
    budget_eth: 5.0,
    description: "",
    deadline: "",
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
      const payload: any = {
        target_software: form.target_software,
        desired_impact: form.desired_impact,
        budget_eth: form.budget_eth,
        description: form.description,
      };
      if (form.target_version_constraint)
        payload.target_version_constraint = form.target_version_constraint;
      if (form.desired_vulnerability_class)
        payload.desired_vulnerability_class = form.desired_vulnerability_class;
      if (form.deadline) payload.deadline = form.deadline;

      await createBounty(payload);
      window.location.hash = "#/zk";
    } catch (err: any) {
      setError(err.message || "Failed to create bounty");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-void-50 mb-4">Post Bounty</h1>

      {error && (
        <div className="text-xs text-red-400 bg-red-900/30 border border-red-800 rounded px-3 py-2 mb-4">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-void-800 border border-void-700 rounded-lg p-5 space-y-4"
      >
        {/* Row: Target Software + Version Constraint */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Target Software</label>
            <input
              type="text"
              required
              value={form.target_software}
              onChange={(e) => update("target_software", e.target.value)}
              placeholder="e.g., OpenSSL"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Version Constraint (optional)</label>
            <input
              type="text"
              value={form.target_version_constraint}
              onChange={(e) =>
                update("target_version_constraint", e.target.value)
              }
              placeholder="e.g., >= 3.0"
              className={inputCls}
            />
          </div>
        </div>

        {/* Row: Desired Impact + Desired Class */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Desired Impact</label>
            <select
              value={form.desired_impact}
              onChange={(e) => update("desired_impact", e.target.value)}
              className={inputCls}
            >
              {IMPACT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>
              Desired Vulnerability Class (optional)
            </label>
            <select
              value={form.desired_vulnerability_class}
              onChange={(e) =>
                update("desired_vulnerability_class", e.target.value)
              }
              className={inputCls}
            >
              <option value="">Any</option>
              {VULN_CLASSES.filter(Boolean).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Budget */}
        <div>
          <label className={labelCls}>Budget (ETH)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            required
            value={form.budget_eth}
            onChange={(e) => update("budget_eth", parseFloat(e.target.value))}
            className={inputCls}
          />
        </div>

        {/* Description */}
        <div>
          <label className={labelCls}>Description</label>
          <textarea
            rows={4}
            required
            value={form.description}
            onChange={(e) => update("description", e.target.value)}
            placeholder="Describe the vulnerability you're looking for..."
            className={inputCls + " resize-none"}
          />
        </div>

        {/* Deadline */}
        <div>
          <label className={labelCls}>Deadline (optional)</label>
          <input
            type="datetime-local"
            value={form.deadline}
            onChange={(e) => update("deadline", e.target.value)}
            className={inputCls}
          />
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 bg-void-500 hover:bg-void-400 text-white rounded font-medium text-sm disabled:opacity-50 transition-colors"
        >
          {submitting ? "Posting..." : "Post Bounty"}
        </button>
      </form>
    </div>
  );
}
