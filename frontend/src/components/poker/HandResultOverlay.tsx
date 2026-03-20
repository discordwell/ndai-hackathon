import { useEffect } from "react";

interface Props {
  result: any | null;
  onDismiss: () => void;
}

export default function HandResultOverlay({ result, onDismiss }: Props) {
  useEffect(() => {
    if (!result) return;
    const timer = setTimeout(onDismiss, 5000);
    return () => clearTimeout(timer);
  }, [result, onDismiss]);

  if (!result) return null;

  const winner = result.winner ?? result.player_id ?? "Unknown";
  const handRank = result.hand_rank ?? result.hand ?? "";
  const amount = result.amount ?? result.pot ?? 0;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center"
      onClick={onDismiss}
    >
      <div
        className="bg-gray-900 border border-gray-600 rounded-2xl p-8 text-center max-w-sm shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-yellow-400 text-2xl font-bold mb-2">Hand Complete</h2>
        <p className="text-white text-lg">
          Winner: <span className="font-semibold">{winner}</span>
        </p>
        {handRank && (
          <p className="text-gray-300 text-sm mt-1">{handRank}</p>
        )}
        {amount > 0 && (
          <p className="text-green-400 text-lg font-bold mt-2">
            Won: {amount.toLocaleString()}
          </p>
        )}
        <button
          onClick={onDismiss}
          className="mt-4 px-4 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
