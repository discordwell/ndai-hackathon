import React, { useState } from "react";
import { createInvention } from "../../api/inventions";
import { FormField } from "../shared/FormField";
import { ValueSlider } from "./ValueSlider";
import type { InventionCreateRequest } from "../../api/types";

const STAGES = ["concept", "prototype", "tested", "production"];

export function InventionForm({ onSuccess }: { onSuccess: () => void }) {
  const [form, setForm] = useState<InventionCreateRequest>({
    title: "",
    anonymized_summary: "",
    category: "",
    full_description: "",
    technical_domain: "",
    novelty_claims: [""],
    prior_art_known: [""],
    potential_applications: [""],
    development_stage: "concept",
    self_assessed_value: 0.5,
    outside_option_value: 0.3,
    confidential_sections: [""],
    max_disclosure_fraction: 0.8,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set<K extends keyof InventionCreateRequest>(
    key: K,
    value: InventionCreateRequest[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateList(
    key: "novelty_claims" | "prior_art_known" | "potential_applications" | "confidential_sections",
    idx: number,
    value: string
  ) {
    const list = [...(form[key] || [])];
    list[idx] = value;
    set(key, list);
  }

  function addToList(
    key: "novelty_claims" | "prior_art_known" | "potential_applications" | "confidential_sections"
  ) {
    set(key, [...(form[key] || []), ""]);
  }

  function removeFromList(
    key: "novelty_claims" | "prior_art_known" | "potential_applications" | "confidential_sections",
    idx: number
  ) {
    const list = [...(form[key] || [])];
    list.splice(idx, 1);
    set(key, list);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      // Filter out empty strings from lists
      const payload = {
        ...form,
        novelty_claims: form.novelty_claims.filter(Boolean),
        prior_art_known: (form.prior_art_known || []).filter(Boolean),
        potential_applications: (form.potential_applications || []).filter(Boolean),
        confidential_sections: (form.confidential_sections || []).filter(Boolean),
      };
      await createInvention(payload);
      onSuccess();
    } catch (err: any) {
      setError(err.detail || "Failed to create invention");
    } finally {
      setLoading(false);
    }
  }

  const inputCls =
    "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm";

  function renderListField(
    label: string,
    key: "novelty_claims" | "prior_art_known" | "potential_applications" | "confidential_sections",
    hint?: string,
    required?: boolean
  ) {
    const items = form[key] || [""];
    return (
      <FormField label={label} required={required} hint={hint}>
        <div className="space-y-2">
          {items.map((item, idx) => (
            <div key={idx} className="flex gap-2">
              <input
                type="text"
                value={item}
                onChange={(e) => updateList(key, idx, e.target.value)}
                className={inputCls}
              />
              {items.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeFromList(key, idx)}
                  className="px-2 text-gray-400 hover:text-red-500"
                >
                  x
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={() => addToList(key)}
            className="text-sm text-ndai-600 hover:text-ndai-700"
          >
            + Add another
          </button>
        </div>
      </FormField>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Basic Info */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h2 className="text-lg font-semibold mb-4">Basic Information</h2>
        <div className="space-y-4">
          <FormField label="Title" required>
            <input
              type="text"
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              required
              className={inputCls}
              placeholder="e.g., Quantum-Resistant Lattice Key Exchange"
            />
          </FormField>
          <FormField
            label="Anonymized Summary"
            hint="Visible to buyers before negotiation — do not include confidential details"
          >
            <textarea
              value={form.anonymized_summary || ""}
              onChange={(e) => set("anonymized_summary", e.target.value)}
              rows={3}
              className={inputCls}
            />
          </FormField>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Category">
              <input
                type="text"
                value={form.category || ""}
                onChange={(e) => set("category", e.target.value)}
                className={inputCls}
                placeholder="e.g., Cryptography"
              />
            </FormField>
            <FormField label="Technical Domain" required>
              <input
                type="text"
                value={form.technical_domain}
                onChange={(e) => set("technical_domain", e.target.value)}
                required
                className={inputCls}
              />
            </FormField>
          </div>
          <FormField label="Development Stage" required>
            <select
              value={form.development_stage}
              onChange={(e) => set("development_stage", e.target.value)}
              className={inputCls}
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </FormField>
        </div>
      </div>

      {/* Description */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h2 className="text-lg font-semibold mb-4">Full Description</h2>
        <FormField
          label="Description"
          required
          hint="This is shared with the AI agent inside the TEE — be thorough"
        >
          <textarea
            value={form.full_description}
            onChange={(e) => set("full_description", e.target.value)}
            required
            rows={6}
            className={inputCls}
          />
        </FormField>
      </div>

      {/* Claims & Context */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h2 className="text-lg font-semibold mb-4">Claims & Context</h2>
        <div className="space-y-4">
          {renderListField("Novelty Claims", "novelty_claims", undefined, true)}
          {renderListField("Known Prior Art", "prior_art_known")}
          {renderListField("Potential Applications", "potential_applications")}
        </div>
      </div>

      {/* Confidential Sections */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h2 className="text-lg font-semibold mb-4">Confidentiality</h2>
        <div className="space-y-4">
          {renderListField(
            "Confidential Sections",
            "confidential_sections",
            "Aspects that must stay within the TEE"
          )}
        </div>
      </div>

      {/* Value Parameters */}
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        <h2 className="text-lg font-semibold mb-4">Value Parameters</h2>
        <div className="space-y-6">
          <ValueSlider
            label="Self-Assessed Value (omega)"
            value={form.self_assessed_value}
            onChange={(v) => set("self_assessed_value", v)}
            hint="Your assessment of the invention's normalized value (0 = worthless, 1 = maximum)"
          />
          <ValueSlider
            label="Outside Option Value (alpha_0)"
            value={form.outside_option_value}
            onChange={(v) => set("outside_option_value", v)}
            hint="Your best alternative if this negotiation fails"
          />
          <ValueSlider
            label="Max Disclosure Fraction"
            value={form.max_disclosure_fraction || 0.8}
            onChange={(v) => set("max_disclosure_fraction", v)}
            hint="Maximum fraction of the invention you're willing to disclose"
          />
        </div>
      </div>

      <div className="flex gap-4">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium"
        >
          {loading ? "Submitting..." : "Submit Invention"}
        </button>
        <a
          href="#/seller/inventions"
          className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
        >
          Cancel
        </a>
      </div>
    </form>
  );
}
