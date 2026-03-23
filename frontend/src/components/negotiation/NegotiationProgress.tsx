import React, { useEffect, useRef } from "react";
import type { NegotiationPhase, ProgressEntry } from "../../hooks/useNegotiationStream";

const STEPS = [
  { key: "seller_disclosure", label: "Seller Disclosure" },
  { key: "buyer_evaluation", label: "Buyer Evaluation" },
  { key: "nash_resolution", label: "Nash Resolution" },
  { key: "complete", label: "Complete" },
] as const;

function phaseIndex(phase: NegotiationPhase | null): number {
  if (!phase || phase === "started") return -1;
  if (phase === "round") return 2; // rounds are part of nash resolution
  const idx = STEPS.findIndex((s) => s.key === phase);
  return idx >= 0 ? idx : -1;
}

export function NegotiationProgress({
  phase,
  progressLog = [],
}: {
  phase: NegotiationPhase | null;
  progressLog?: ProgressEntry[];
}) {
  const activeIdx = phaseIndex(phase);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [progressLog.length]);

  return (
    <div>
      {/* Step indicator */}
      <div className="flex items-center gap-1 py-4">
        {STEPS.map((step, i) => {
          const isComplete = i < activeIdx || phase === "complete";
          const isActive = i === activeIdx && phase !== "complete";

          return (
            <React.Fragment key={step.key}>
              {i > 0 && (
                <div
                  className={`flex-1 h-0.5 transition-colors duration-500 ${
                    i <= activeIdx ? "bg-ndai-500" : "bg-gray-200"
                  }`}
                />
              )}
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all duration-300 ${
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

      {/* Live progress log */}
      {progressLog.length > 0 && (
        <div className="mt-3 bg-gray-50 rounded-lg border border-gray-100 p-3 max-h-48 overflow-y-auto">
          <div className="space-y-1.5">
            {progressLog.map((entry, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-xs animate-fadeSlideUp"
                style={{ animationDelay: `${i * 50}ms`, animationFillMode: "both" }}
              >
                <PhaseIcon phase={entry.phase} done={!!entry.data.done} />
                <span className={entry.data.done ? "text-gray-700" : "text-gray-500"}>
                  {entry.message}
                </span>
              </div>
            ))}
          </div>
          <div ref={logEndRef} />
        </div>
      )}
    </div>
  );
}

function PhaseIcon({ phase, done }: { phase: NegotiationPhase; done: boolean }) {
  if (done) {
    return (
      <svg className="w-3.5 h-3.5 text-green-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    );
  }

  const colors: Record<string, string> = {
    seller_disclosure: "text-blue-400",
    buyer_evaluation: "text-amber-400",
    nash_resolution: "text-purple-400",
    round: "text-indigo-400",
    started: "text-gray-400",
    complete: "text-green-500",
  };

  return (
    <svg className={`w-3.5 h-3.5 ${colors[phase] || "text-gray-400"} mt-0.5 flex-shrink-0 animate-spin`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}
