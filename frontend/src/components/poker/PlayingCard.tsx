import type { PlayingCard as PlayingCardType } from "../../api/pokerTypes";

const SUIT_SYMBOLS = ["\u2663", "\u2666", "\u2665", "\u2660"] as const;
const SUIT_COLORS = ["text-gray-900", "text-red-500", "text-red-500", "text-gray-900"] as const;
const SUIT_NAMES = ["clubs", "diamonds", "hearts", "spades"] as const;

const RANK_NAMES: Record<number, string> = {
  2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
  11: "J", 12: "Q", 13: "K", 14: "A",
};

const SIZES = {
  sm: { w: 40, h: 56, rank: 13, suit: 16, corner: 4, pad: 3 },
  md: { w: 58, h: 82, rank: 17, suit: 22, corner: 6, pad: 5 },
  lg: { w: 76, h: 108, rank: 22, suit: 28, corner: 8, pad: 6 },
} as const;

interface Props {
  card: PlayingCardType | null;
  size?: "sm" | "md" | "lg";
}

export default function PlayingCard({ card, size = "md" }: Props) {
  const s = SIZES[size];

  if (!card) {
    // Face-down card back
    return (
      <div
        style={{ width: s.w, height: s.h }}
        className="relative rounded-lg overflow-hidden shadow-lg"
      >
        {/* Card back with diamond pattern */}
        <div className="absolute inset-0 bg-gradient-to-br from-ndai-700 via-ndai-800 to-ndai-900" />
        <div className="absolute inset-[3px] rounded-md border border-ndai-500/30"
          style={{
            backgroundImage: `repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(255,255,255,0.03) 4px, rgba(255,255,255,0.03) 5px),
              repeating-linear-gradient(-45deg, transparent, transparent 4px, rgba(255,255,255,0.03) 4px, rgba(255,255,255,0.03) 5px)`,
          }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-5 h-5 rounded-full border border-ndai-400/40 flex items-center justify-center">
            <span className="text-ndai-400/50 text-[8px] font-bold">TK</span>
          </div>
        </div>
      </div>
    );
  }

  const rank = RANK_NAMES[card.rank] ?? "?";
  const suitSymbol = SUIT_SYMBOLS[card.suit] ?? "?";
  const color = SUIT_COLORS[card.suit] ?? "text-gray-900";
  const isRed = card.suit === 1 || card.suit === 2;

  return (
    <div
      style={{ width: s.w, height: s.h }}
      className={`relative rounded-lg overflow-hidden shadow-lg transition-transform duration-200 hover:-translate-y-0.5 ${color}`}
    >
      {/* Card face */}
      <div className="absolute inset-0 bg-gradient-to-br from-white via-gray-50 to-gray-100" />
      <div className="absolute inset-[1px] rounded-md border border-gray-200/60" />

      {/* Top-left corner */}
      <div className="absolute flex flex-col items-center leading-none" style={{ top: s.pad, left: s.pad }}>
        <span className="font-bold" style={{ fontSize: s.rank }}>{rank}</span>
        <span style={{ fontSize: s.suit * 0.7 }}>{suitSymbol}</span>
      </div>

      {/* Center suit */}
      <div className="absolute inset-0 flex items-center justify-center">
        <span style={{ fontSize: s.suit * 1.3 }} className={isRed ? "drop-shadow-[0_1px_1px_rgba(239,68,68,0.2)]" : "drop-shadow-[0_1px_1px_rgba(0,0,0,0.1)]"}>
          {suitSymbol}
        </span>
      </div>

      {/* Bottom-right corner (rotated) */}
      <div className="absolute flex flex-col items-center leading-none rotate-180" style={{ bottom: s.pad, right: s.pad }}>
        <span className="font-bold" style={{ fontSize: s.rank }}>{rank}</span>
        <span style={{ fontSize: s.suit * 0.7 }}>{suitSymbol}</span>
      </div>

      {/* Subtle sheen */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/30 via-transparent to-transparent pointer-events-none" />
    </div>
  );
}
