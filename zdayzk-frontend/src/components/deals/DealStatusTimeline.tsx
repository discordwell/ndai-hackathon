import React from "react";
import type { NegotiationEvent } from "../../hooks/useNegotiationStream";

const PHASES = [
  { key: "started", label: "Started" },
  { key: "seller_disclosure", label: "Seller Disclosure" },
  { key: "buyer_evaluation", label: "Buyer Evaluation" },
  { key: "nash_resolution", label: "Nash Resolution" },
  { key: "complete", label: "Complete" },
];

interface Props {
  events: NegotiationEvent[];
}

export function DealStatusTimeline({ events }: Props) {
  const completedPhases = new Set(events.map((e) => e.phase));
  const latestPhase = events.length > 0 ? events[events.length - 1].phase : null;

  return (
    <div className="space-y-0">
      {PHASES.map((phase, i) => {
        const isDone = completedPhases.has(phase.key);
        const isActive = latestPhase === phase.key && phase.key !== "complete";
        const isPending = !isDone && !isActive;

        return (
          <div key={phase.key} className="flex items-start gap-3">
            {/* Connector */}
            <div className="flex flex-col items-center">
              <div
                className={`w-3 h-3 rounded-full border-2 flex-shrink-0 ${
                  isDone
                    ? "bg-accent-400 border-accent-400"
                    : isActive
                    ? "border-accent-400 bg-transparent animate-pulse"
                    : "border-surface-600 bg-transparent"
                }`}
              />
              {i < PHASES.length - 1 && (
                <div
                  className={`w-px h-8 ${
                    isDone ? "bg-accent-400/40" : "bg-surface-700"
                  }`}
                />
              )}
            </div>

            {/* Label */}
            <div className="pb-4">
              <p
                className={`text-xs font-medium ${
                  isDone
                    ? "text-accent-400"
                    : isActive
                    ? "text-white"
                    : "text-gray-600"
                }`}
              >
                {phase.label}
              </p>
              {isDone && phase.key === "complete" && (
                <p className="text-[10px] text-gray-500 mt-0.5">
                  {events.find((e) => e.phase === "complete")?.data.outcome as string}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
