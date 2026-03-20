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

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span
      className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[9px] font-bold text-white ${color}`}
    >
      {label}
    </span>
  );
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
      <div className="w-28 h-24 rounded-xl border-2 border-dashed border-gray-600 flex items-center justify-center opacity-40">
        <span className="text-gray-500 text-xs">Empty</span>
      </div>
    );
  }

  const isFolded = !seat.is_active && seat.has_hole_cards === false;
  const isAllIn = seat.stack === 0 && seat.is_active;
  const displayName = seat.player_id.length > 8
    ? seat.player_id.slice(0, 6) + "\u2026"
    : seat.player_id;

  return (
    <div
      className={[
        "relative w-28 rounded-xl bg-gray-800/90 border-2 p-2 flex flex-col items-center gap-1",
        isActionOn ? "border-yellow-400 animate-pulse" : "border-gray-600",
        isAllIn ? "shadow-[0_0_12px_rgba(239,68,68,0.6)]" : "",
        isFolded ? "opacity-50" : "",
      ].join(" ")}
    >
      {/* Chip indicators */}
      <div className="absolute -top-2 -right-1 flex gap-0.5">
        {isDealer && <Chip label="D" color="bg-yellow-500" />}
        {isSmallBlind && <Chip label="SB" color="bg-blue-500" />}
        {isBigBlind && <Chip label="BB" color="bg-orange-500" />}
      </div>

      {/* Hole cards */}
      <div className="flex gap-0.5">
        {isHero && seat.hole_cards ? (
          seat.hole_cards.map((c, i) => <PlayingCard key={i} card={c} size="sm" />)
        ) : seat.has_hole_cards ? (
          <>
            <PlayingCard card={null} size="sm" />
            <PlayingCard card={null} size="sm" />
          </>
        ) : null}
      </div>

      {/* Name and stack */}
      <span className="text-white text-xs font-medium truncate max-w-full">{displayName}</span>
      <span className="text-gray-300 text-[10px]">
        {isAllIn ? "ALL IN" : seat.stack.toLocaleString()}
      </span>

      {/* Current bet */}
      {seat.current_bet > 0 && (
        <span className="absolute -bottom-4 text-yellow-300 text-[10px] font-bold">
          Bet: {seat.current_bet.toLocaleString()}
        </span>
      )}
    </div>
  );
}
