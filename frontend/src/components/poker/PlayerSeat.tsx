import type { SeatView } from "../../api/pokerTypes";
import PlayingCard from "./PlayingCard";

interface Props {
  seat: SeatView | null;
  isHero: boolean;
  isDealer: boolean;
  isSmallBlind: boolean;
  isBigBlind: boolean;
  isActionOn?: boolean;
}

function DealerChip({ label, bg }: { label: string; bg: string }) {
  return (
    <div className={`w-6 h-6 rounded-full ${bg} flex items-center justify-center shadow-md border border-white/20`}>
      <span className="text-[9px] font-black text-white leading-none">{label}</span>
    </div>
  );
}

function formatStack(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 10_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

// Generate a consistent avatar color from player ID
function avatarColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash);
  const colors = [
    "from-emerald-500 to-teal-600",
    "from-blue-500 to-indigo-600",
    "from-purple-500 to-violet-600",
    "from-rose-500 to-pink-600",
    "from-amber-500 to-orange-600",
    "from-cyan-500 to-sky-600",
    "from-fuchsia-500 to-purple-600",
    "from-lime-500 to-green-600",
  ];
  return colors[Math.abs(hash) % colors.length];
}

export default function PlayerSeat({
  seat,
  isHero,
  isDealer,
  isSmallBlind,
  isBigBlind,
  isActionOn = false,
}: Props) {
  if (!seat) {
    return (
      <div className="w-32 h-20 rounded-2xl border border-dashed border-white/10 flex items-center justify-center">
        <span className="text-white/20 text-xs tracking-wide uppercase">Open</span>
      </div>
    );
  }

  const isFolded = !seat.is_active;
  const isAllIn = seat.stack === 0 && seat.is_active;
  const displayName = isHero ? "You" : seat.player_id.slice(0, 6) + "\u2026";
  const avatarGrad = avatarColor(seat.player_id);
  const initial = isHero ? "U" : seat.player_id.charAt(0).toUpperCase();

  return (
    <div className="flex flex-col items-center gap-1.5">
      {/* Bet display - above the seat */}
      {seat.current_bet > 0 && (
        <div className="flex items-center gap-1.5 mb-0.5">
          <div className="w-4 h-4 rounded-full bg-gradient-to-b from-gold-400 to-gold-600 shadow-sm border border-gold-300/50" />
          <span className="text-gold-400 text-xs font-bold tabular-nums">
            {formatStack(seat.current_bet)}
          </span>
        </div>
      )}

      {/* Main seat container */}
      <div
        className={[
          "relative rounded-2xl p-2.5 flex flex-col items-center gap-1 transition-all duration-300",
          isHero ? "bg-gray-800/95 backdrop-blur-sm" : "bg-gray-900/90 backdrop-blur-sm",
          isActionOn
            ? "ring-2 ring-gold-400 shadow-[0_0_20px_rgba(212,168,67,0.3)]"
            : "ring-1 ring-white/10",
          isAllIn ? "ring-2 ring-red-500 shadow-[0_0_16px_rgba(239,68,68,0.3)]" : "",
          isFolded ? "opacity-40" : "",
        ].join(" ")}
        style={{ minWidth: 120 }}
      >
        {/* Dealer/blind chips */}
        <div className="absolute -top-2.5 -right-2 flex gap-1">
          {isDealer && <DealerChip label="D" bg="bg-gradient-to-b from-yellow-400 to-yellow-600" />}
          {isSmallBlind && <DealerChip label="SB" bg="bg-gradient-to-b from-blue-400 to-blue-600" />}
          {isBigBlind && <DealerChip label="BB" bg="bg-gradient-to-b from-orange-400 to-orange-600" />}
        </div>

        {/* Hole cards */}
        <div className="flex -space-x-2">
          {isHero && seat.hole_cards && seat.hole_cards.length > 0 ? (
            seat.hole_cards.map((c, i) => (
              <div key={i} className={i === 1 ? "rotate-3" : "-rotate-3"}>
                <PlayingCard card={c} size="sm" />
              </div>
            ))
          ) : seat.has_hole_cards ? (
            <>
              <div className="-rotate-3"><PlayingCard card={null} size="sm" /></div>
              <div className="rotate-3"><PlayingCard card={null} size="sm" /></div>
            </>
          ) : null}
        </div>

        {/* Player info row */}
        <div className="flex items-center gap-2 mt-0.5">
          {/* Avatar */}
          <div className={`w-7 h-7 rounded-full bg-gradient-to-br ${avatarGrad} flex items-center justify-center shadow-inner`}>
            <span className="text-white text-[10px] font-bold">{initial}</span>
          </div>

          <div className="flex flex-col items-start">
            <span className={`text-xs font-semibold leading-tight ${isHero ? "text-white" : "text-gray-300"}`}>
              {displayName}
            </span>
            <span className={`text-[11px] font-mono leading-tight tabular-nums ${isAllIn ? "text-red-400 font-bold" : "text-gray-400"}`}>
              {isAllIn ? "ALL IN" : formatStack(seat.stack)}
            </span>
          </div>
        </div>

        {/* Action timer bar */}
        {isActionOn && (
          <div className="absolute -bottom-0.5 left-3 right-3 h-0.5 rounded-full overflow-hidden bg-gray-700">
            <div className="h-full bg-gradient-to-r from-gold-400 to-gold-500 rounded-full animate-[shrink_30s_linear]"
              style={{ animation: "shrink 30s linear forwards" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
