import React from "react";
import type { VulnOutcome } from "../../hooks/useNegotiationStream";

export function OutcomeCard({ outcome }: { outcome: VulnOutcome }) {
  const isDeal = outcome.outcome === "agreement" || outcome.outcome === "deal";

  return (
    <div
      className={`glass-card p-6 border ${
        isDeal ? "border-success-500/30" : "border-danger-500/30"
      }`}
    >
      <div className="flex items-center gap-3 mb-4">
        <span
          className={`w-8 h-8 rounded-full flex items-center justify-center ${
            isDeal ? "bg-success-500/20 text-success-400" : "bg-danger-500/20 text-danger-400"
          }`}
        >
          {isDeal ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
        </span>
        <div>
          <h3 className={`text-sm font-semibold ${isDeal ? "text-success-400" : "text-danger-400"}`}>
            {isDeal ? "Deal Reached" : "No Deal"}
          </h3>
          {outcome.reason && (
            <p className="text-xs text-gray-500">{outcome.reason}</p>
          )}
        </div>
      </div>

      {isDeal && outcome.final_price != null && (
        <div className="grid grid-cols-3 gap-4 mt-4">
          <div className="bg-surface-800/50 rounded-lg p-3">
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Final Price</span>
            <p className="text-lg font-bold text-accent-400 font-mono mt-1">
              {outcome.final_price.toFixed(4)}
            </p>
          </div>
          {outcome.disclosure_level != null && (
            <div className="bg-surface-800/50 rounded-lg p-3">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">Disclosure Level</span>
              <p className="text-lg font-bold text-white font-mono mt-1">
                {outcome.disclosure_level}/3
              </p>
            </div>
          )}
          {outcome.negotiation_rounds != null && (
            <div className="bg-surface-800/50 rounded-lg p-3">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">Rounds</span>
              <p className="text-lg font-bold text-white font-mono mt-1">
                {outcome.negotiation_rounds}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
