import React, { useState } from "react";
import { CopyButton } from "./CopyButton";

interface PolicyConstraint {
  field: string;
  pattern: string | null;
  deny_patterns: string[];
  max_length: number | null;
  rationale: string;
}

interface FieldResult {
  field: string;
  passed: boolean;
  violations: string[];
}

interface PolicyReport {
  all_passed: boolean;
  results: FieldResult[];
  policy_hash: string;
}

interface Props {
  report: PolicyReport | null | undefined;
  constraints: PolicyConstraint[] | null | undefined;
}

export function PolicyDisplay({ report, constraints, defaultExpanded = true }: Props & { defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (!report) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <span className={`text-lg ${report.all_passed ? "text-green-600" : "text-red-500"}`}>
            {report.all_passed ? "\u2713" : "\u2717"}
          </span>
          <h3 className="font-semibold text-gray-900">Policy Enforcement</h3>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              report.all_passed
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {report.all_passed ? "All Passed" : "Violations Found"}
          </span>
        </div>
        <span className="text-xs text-gray-400">{expanded ? "collapse" : "expand"}</span>
      </button>

      <div className="mt-2 flex items-center gap-1">
        <span className="text-xs text-gray-500">Policy hash:</span>
        <CopyButton value={report.policy_hash} truncateLength={24} />
      </div>

      {expanded && (
        <div className="mt-4 border-t border-gray-100 pt-4 space-y-3">
          {report.results.map((result, i) => (
            <div key={i} className="text-sm">
              <div className="flex items-center gap-2">
                <span className={result.passed ? "text-green-500" : "text-red-500"}>
                  {result.passed ? "\u2713" : "\u2717"}
                </span>
                <span className="font-medium text-gray-900">{result.field}</span>
              </div>
              {result.violations.length > 0 && (
                <ul className="ml-6 mt-1 space-y-0.5">
                  {result.violations.map((v, j) => (
                    <li key={j} className="text-xs text-red-600">{v}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}

          {constraints && constraints.length > 0 && (
            <div className="border-t border-gray-100 pt-3">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Constraints Applied
              </h4>
              <div className="space-y-2">
                {constraints.map((c, i) => (
                  <div key={i} className="text-xs bg-gray-50 rounded p-2">
                    <span className="font-medium text-gray-800">{c.field}</span>
                    {c.max_length && (
                      <span className="text-gray-500 ml-2">max: {c.max_length}</span>
                    )}
                    {c.pattern && (
                      <span className="text-gray-500 ml-2">
                        pattern: <code className="font-mono">{c.pattern}</code>
                      </span>
                    )}
                    {c.deny_patterns.length > 0 && (
                      <span className="text-gray-500 ml-2">
                        deny: {c.deny_patterns.length} pattern(s)
                      </span>
                    )}
                    {c.rationale && (
                      <p className="text-gray-400 mt-0.5 italic">{c.rationale}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
