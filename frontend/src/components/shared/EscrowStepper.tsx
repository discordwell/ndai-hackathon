import React from "react";

interface Props {
  state: string; // Funded, Evaluated, Accepted, Rejected, Expired
  creationTxHash?: string;
  outcomeTxHash?: string;
  settlementTxHash?: string;
}

// STATE_ORDER: Created=-1, Funded=0, Evaluated=1, Accepted/Rejected/Expired=2
const STATE_ORDER: Record<string, number> = {
  Created: -1,
  Funded: 0,
  Evaluated: 1,
  Accepted: 2,
  Rejected: 2,
  Expired: 2,
};

function truncateHash(hash: string): string {
  return hash.slice(0, 6) + "..." + hash.slice(-4);
}

function terminalLabel(state: string): string {
  if (state === "Accepted") return "Accepted";
  if (state === "Rejected") return "Rejected";
  if (state === "Expired") return "Expired";
  return "Outcome";
}

function terminalColor(state: string): string {
  if (state === "Accepted") return "text-green-600";
  if (state === "Rejected") return "text-red-600";
  if (state === "Expired") return "text-gray-400";
  return "text-gray-400";
}

function terminalCircleColor(state: string, isComplete: boolean, isActive: boolean): string {
  if (!isComplete && !isActive) return "bg-gray-100 text-gray-400";
  if (state === "Accepted") return "bg-green-500 text-white";
  if (state === "Rejected") return "bg-red-500 text-white";
  if (state === "Expired") return "bg-gray-400 text-white";
  return "bg-ndai-500 text-white";
}

export function EscrowStepper({ state, creationTxHash, outcomeTxHash, settlementTxHash }: Props) {
  const activeIdx = STATE_ORDER[state] ?? -1;

  const STEPS = [
    { key: "funded", label: "Funded", txHash: creationTxHash },
    { key: "evaluated", label: "Evaluated", txHash: outcomeTxHash },
    { key: "terminal", label: terminalLabel(state), txHash: settlementTxHash },
  ] as const;

  return (
    <div className="flex items-start gap-1 py-4">
      {STEPS.map((step, i) => {
        const isTerminal = i === 2;
        const isComplete = isTerminal
          ? activeIdx >= 2
          : i < activeIdx;
        const isActive = !isComplete && i === activeIdx;

        const circleClass = isTerminal
          ? terminalCircleColor(state, isComplete, isActive)
          : isComplete
            ? "bg-ndai-500 text-white"
            : isActive
              ? "bg-ndai-100 text-ndai-700 ring-2 ring-ndai-500 animate-pulse"
              : "bg-gray-100 text-gray-400";

        const labelClass = isTerminal && isComplete
          ? terminalColor(state) + " font-medium"
          : isComplete || isActive
            ? "text-ndai-700 font-medium"
            : "text-gray-400";

        return (
          <React.Fragment key={step.key}>
            {i > 0 && (
              <div
                className={`flex-1 h-0.5 mt-4 ${
                  i <= activeIdx ? "bg-ndai-500" : "bg-gray-200"
                }`}
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all ${circleClass}`}
              >
                {isComplete ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span className={`text-xs whitespace-nowrap ${labelClass}`}>
                {step.label}
              </span>
              {isComplete && step.txHash && (
                <a
                  href={`https://sepolia.basescan.org/tx/${step.txHash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-ndai-500 hover:text-ndai-700 underline font-mono"
                >
                  {truncateHash(step.txHash)}
                </a>
              )}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}
