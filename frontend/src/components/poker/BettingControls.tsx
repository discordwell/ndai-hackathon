import { useState, useEffect } from "react";

interface Props {
  callAmount: number;
  minRaise: number;
  maxRaise: number;
  canCheck: boolean;
  onAction: (action: string, amount?: number) => void;
  disabled: boolean;
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

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-gray-900/95 border-t border-gray-700 px-4 py-3 flex items-center gap-3 z-50">
      {/* Fold */}
      <button
        disabled={disabled}
        onClick={() => onAction("fold")}
        className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-sm disabled:opacity-40"
      >
        Fold
      </button>

      {/* Check or Call */}
      {canCheck ? (
        <button
          disabled={disabled}
          onClick={() => onAction("check")}
          className="px-4 py-2 rounded-lg bg-gray-600 hover:bg-gray-700 text-white font-semibold text-sm disabled:opacity-40"
        >
          Check
        </button>
      ) : (
        <button
          disabled={disabled}
          onClick={() => onAction("call")}
          className="px-4 py-2 rounded-lg bg-ndai-600 hover:bg-ndai-700 text-white font-semibold text-sm disabled:opacity-40"
        >
          Call {callAmount.toLocaleString()}
        </button>
      )}

      {/* Raise section */}
      {minRaise < maxRaise && (
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <input
            type="range"
            min={minRaise}
            max={maxRaise}
            value={raiseAmount}
            onChange={(e) => handleRaiseChange(Number(e.target.value))}
            disabled={disabled}
            className="flex-1 accent-ndai-500"
          />
          <input
            type="number"
            min={minRaise}
            max={maxRaise}
            value={raiseAmount}
            onChange={(e) => handleRaiseChange(Number(e.target.value))}
            disabled={disabled}
            className="w-20 px-2 py-1 rounded bg-gray-800 border border-gray-600 text-white text-sm text-center"
          />
          <button
            disabled={disabled}
            onClick={() => onAction("raise", raiseAmount)}
            className="px-4 py-2 rounded-lg bg-ndai-600 hover:bg-ndai-700 text-white font-semibold text-sm disabled:opacity-40"
          >
            Raise
          </button>
        </div>
      )}

      {/* All In */}
      <button
        disabled={disabled}
        onClick={() => onAction("all_in")}
        className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white font-semibold text-sm disabled:opacity-40 ml-auto"
      >
        All In
      </button>
    </div>
  );
}
