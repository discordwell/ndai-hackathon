import { useState, useEffect } from "react";

interface Props {
  callAmount: number;
  minRaise: number;
  maxRaise: number;
  canCheck: boolean;
  onAction: (action: string, amount?: number) => void;
  disabled: boolean;
}

function formatChips(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 10_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

export default function BettingControls({
  callAmount,
  minRaise,
  maxRaise,
  canCheck,
  onAction,
  disabled,
}: Props) {
  const [raiseAmount, setRaiseAmount] = useState(minRaise);

  useEffect(() => {
    setRaiseAmount(minRaise);
  }, [minRaise]);

  const handleRaiseChange = (val: number) => {
    setRaiseAmount(Math.min(Math.max(val, minRaise), maxRaise));
  };

  const potSize = callAmount > 0 ? callAmount * 2 : minRaise;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50">
      {/* Gradient fade */}
      <div className="h-6 bg-gradient-to-t from-gray-950 to-transparent" />

      <div className="bg-gray-950/98 backdrop-blur-md border-t border-white/5 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center gap-3">
          {/* Fold */}
          <button
            disabled={disabled}
            onClick={() => onAction("fold")}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-b from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white font-bold text-sm shadow-lg shadow-red-900/30 disabled:opacity-30 transition-all active:scale-95 border border-red-500/30"
          >
            Fold
          </button>

          {/* Check or Call */}
          {canCheck ? (
            <button
              disabled={disabled}
              onClick={() => onAction("check")}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-b from-gray-600 to-gray-700 hover:from-gray-500 hover:to-gray-600 text-white font-bold text-sm shadow-lg disabled:opacity-30 transition-all active:scale-95 border border-gray-500/30"
            >
              Check
            </button>
          ) : (
            <button
              disabled={disabled}
              onClick={() => onAction("call")}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-b from-ndai-600 to-ndai-700 hover:from-ndai-500 hover:to-ndai-600 text-white font-bold text-sm shadow-lg shadow-ndai-900/30 disabled:opacity-30 transition-all active:scale-95 border border-ndai-500/30"
            >
              Call {formatChips(callAmount)}
            </button>
          )}

          {/* Raise section */}
          {minRaise < maxRaise && (
            <>
              <div className="h-8 w-px bg-white/10 mx-1" />

              <div className="flex items-center gap-2 flex-1 max-w-sm">
                {/* Quick bet buttons */}
                <div className="flex gap-1">
                  {[
                    { label: "Min", val: minRaise },
                    { label: "\u00BD", val: Math.floor(potSize / 2) },
                    { label: "Pot", val: potSize },
                  ].map(({ label, val }) => (
                    <button
                      key={label}
                      disabled={disabled}
                      onClick={() => handleRaiseChange(Math.max(val, minRaise))}
                      className="px-2 py-1 rounded-md bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white text-[10px] font-medium transition-colors disabled:opacity-30 border border-white/5"
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {/* Slider */}
                <input
                  type="range"
                  min={minRaise}
                  max={maxRaise}
                  value={raiseAmount}
                  onChange={(e) => handleRaiseChange(Number(e.target.value))}
                  disabled={disabled}
                  className="flex-1 h-1.5 accent-gold-400 cursor-pointer disabled:opacity-30"
                />

                {/* Amount input */}
                <input
                  type="number"
                  min={minRaise}
                  max={maxRaise}
                  value={raiseAmount}
                  onChange={(e) => handleRaiseChange(Number(e.target.value))}
                  disabled={disabled}
                  className="w-20 px-2 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white text-sm text-center font-mono tabular-nums focus:outline-none focus:ring-1 focus:ring-gold-500/50 disabled:opacity-30"
                />

                {/* Raise button */}
                <button
                  disabled={disabled}
                  onClick={() => onAction("raise", raiseAmount)}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-b from-gold-500 to-gold-600 hover:from-gold-400 hover:to-gold-500 text-gray-900 font-bold text-sm shadow-lg shadow-gold-900/20 disabled:opacity-30 transition-all active:scale-95 border border-gold-400/30"
                >
                  Raise
                </button>
              </div>
            </>
          )}

          {/* All In */}
          <div className="ml-auto">
            <button
              disabled={disabled}
              onClick={() => onAction("all_in")}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-b from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-white font-bold text-sm shadow-lg shadow-emerald-900/30 disabled:opacity-30 transition-all active:scale-95 border border-emerald-400/30"
            >
              All In
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
