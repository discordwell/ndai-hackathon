import React from "react";

function getColor(cvss: number): string {
  if (cvss >= 9) return "text-danger-400";
  if (cvss >= 7) return "text-orange-400";
  if (cvss >= 4) return "text-accent-400";
  return "text-gray-400";
}

function getLabel(cvss: number): string {
  if (cvss >= 9) return "Critical";
  if (cvss >= 7) return "High";
  if (cvss >= 4) return "Medium";
  return "Low";
}

export function SeverityMeter({ cvss }: { cvss: number }) {
  const pct = Math.min(100, (cvss / 10) * 100);
  const color = getColor(cvss);

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            cvss >= 9
              ? "bg-danger-400"
              : cvss >= 7
              ? "bg-orange-400"
              : cvss >= 4
              ? "bg-accent-400"
              : "bg-gray-500"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-medium ${color}`}>
        {cvss.toFixed(1)}
      </span>
      <span className={`text-[10px] ${color}`}>{getLabel(cvss)}</span>
    </div>
  );
}
