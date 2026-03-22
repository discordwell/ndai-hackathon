import { useEffect } from "react";

interface Props {
  result: any | null;
  onDismiss: () => void;
}

export default function HandResultOverlay({ result, onDismiss }: Props) {
  useEffect(() => {
    if (!result) return;
    const timer = setTimeout(onDismiss, 6000);
    return () => clearTimeout(timer);
  }, [result, onDismiss]);

  if (!result) return null;

  const winner = result.winner ?? result.player_id ?? "Unknown";
  const displayWinner = winner.length > 10 ? winner.slice(0, 8) + "\u2026" : winner;
  const handRank = result.hand_rank ?? result.hand ?? "";
  const amount = result.amount ?? result.pot ?? 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center animate-[fadeIn_0.3s_ease-out]"
      onClick={onDismiss}
    >
      {/* Backdrop with radial glow */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-96 h-96 bg-gold-500/10 rounded-full blur-[100px]" />
      </div>

      <div
        className="relative max-w-sm w-full mx-4 animate-[scaleIn_0.4s_ease-out]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Card */}
        <div className="bg-gradient-to-b from-gray-800 to-gray-900 rounded-2xl border border-white/10 overflow-hidden shadow-2xl">
          {/* Gold accent bar */}
          <div className="h-1 bg-gradient-to-r from-transparent via-gold-400 to-transparent" />

          <div className="p-8 text-center">
            {/* Trophy icon */}
            <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-gradient-to-b from-gold-400/20 to-gold-600/10 border border-gold-500/30 flex items-center justify-center">
              <span className="text-2xl">&#x1F3C6;</span>
            </div>

            <h2 className="text-gold-400 text-xl font-bold tracking-wide uppercase mb-1">
              Winner
            </h2>

            <p className="text-white text-lg font-semibold mb-1">
              {displayWinner}
            </p>

            {handRank && (
              <p className="text-gray-400 text-sm tracking-wide">{handRank}</p>
            )}

            {amount > 0 && (
              <div className="mt-4 inline-flex items-center gap-2 bg-white/5 rounded-full px-5 py-2 border border-white/5">
                <div className="w-3 h-3 rounded-full bg-gradient-to-b from-gold-400 to-gold-600" />
                <span className="text-emerald-400 text-lg font-bold tabular-nums">
                  +{amount.toLocaleString()}
                </span>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-8 pb-6">
            <button
              onClick={onDismiss}
              className="w-full py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 text-sm transition-colors border border-white/5"
            >
              Continue
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
