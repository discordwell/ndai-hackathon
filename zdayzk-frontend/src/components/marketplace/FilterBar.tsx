import React from "react";

export interface Filters {
  impactType: string;
  minCvss: number;
  exclusivity: string;
}

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function FilterBar({ filters, onChange }: Props) {
  const impactTypes = ["All", "RCE", "LPE", "InfoLeak", "DoS"];
  const exclusivities = ["All", "exclusive", "non-exclusive"];

  return (
    <div className="flex flex-wrap items-center gap-3 mb-6">
      {/* Impact type pills */}
      <div className="flex items-center gap-1">
        {impactTypes.map((t) => {
          const active = (t === "All" && !filters.impactType) || filters.impactType === t;
          return (
            <button
              key={t}
              onClick={() => onChange({ ...filters, impactType: t === "All" ? "" : t })}
              className={`px-2.5 py-1 text-[11px] font-medium rounded transition-all ${
                active
                  ? "bg-accent-400/20 text-accent-400 border border-accent-400/30"
                  : "text-gray-500 border border-surface-700 hover:border-surface-600 hover:text-gray-300"
              }`}
            >
              {t}
            </button>
          );
        })}
      </div>

      {/* CVSS minimum */}
      <div className="flex items-center gap-2 text-xs text-gray-400">
        <span>CVSS &ge;</span>
        <input
          type="range"
          min={0}
          max={10}
          step={0.5}
          value={filters.minCvss}
          onChange={(e) => onChange({ ...filters, minCvss: parseFloat(e.target.value) })}
          className="w-24 accent-accent-400"
        />
        <span className="font-mono text-accent-400 w-6">{filters.minCvss}</span>
      </div>

      {/* Exclusivity */}
      <select
        value={filters.exclusivity || "All"}
        onChange={(e) =>
          onChange({ ...filters, exclusivity: e.target.value === "All" ? "" : e.target.value })
        }
        className="text-[11px] bg-surface-800 border border-surface-700 text-gray-300 rounded px-2 py-1 outline-none focus:border-accent-500/40"
      >
        {exclusivities.map((e) => (
          <option key={e} value={e}>{e}</option>
        ))}
      </select>
    </div>
  );
}
