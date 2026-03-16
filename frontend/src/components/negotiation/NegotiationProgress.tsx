import React from "react";
import type { NegotiationPhase } from "../../hooks/useNegotiationStream";

const STEPS = [
  { key: "seller_disclosure", label: "Seller Disclosure" },
  { key: "buyer_evaluation", label: "Buyer Evaluation" },
  { key: "nash_resolution", label: "Nash Resolution" },
  { key: "complete", label: "Complete" },
] as const;

function phaseIndex(phase: NegotiationPhase | null): number {
  if (!phase || phase === "started") return -1;
  const idx = STEPS.findIndex((s) => s.key === phase);
  return idx >= 0 ? idx : -1;
}

export function NegotiationProgress({
  phase,
}: {
  phase: NegotiationPhase | null;
}) {
  const activeIdx = phaseIndex(phase);

  return (
    <div className="flex items-center gap-1 py-4">
      {STEPS.map((step, i) => {
        const isComplete = i < activeIdx || phase === "complete";
        const isActive = i === activeIdx && phase !== "complete";

        return (
          <React.Fragment key={step.key}>
            {i > 0 && (
              <div
                className={`flex-1 h-0.5 ${
                  i <= activeIdx ? "bg-ndai-500" : "bg-gray-200"
                }`}
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all ${
                  isComplete
                    ? "bg-ndai-500 text-white"
                    : isActive
                      ? "bg-ndai-100 text-ndai-700 ring-2 ring-ndai-500 animate-pulse"
                      : "bg-gray-100 text-gray-400"
                }`}
              >
                {isComplete ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={`text-xs whitespace-nowrap ${
                  isComplete || isActive ? "text-ndai-700 font-medium" : "text-gray-400"
                }`}
              >
                {step.label}
              </span>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}
