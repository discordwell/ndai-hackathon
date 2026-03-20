import type { PlayingCard as PlayingCardType } from "../../api/pokerTypes";

const SUIT_SYMBOLS = ["\u2663", "\u2666", "\u2665", "\u2660"] as const;
const SUIT_COLORS = ["text-black", "text-red-600", "text-red-600", "text-black"] as const;

const RANK_NAMES: Record<number, string> = {
  2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10",
  11: "J", 12: "Q", 13: "K", 14: "A",
};

const SIZES = {
  sm: { w: "w-10", h: "h-14", text: "text-xs", suit: "text-sm" },
  md: { w: "w-14", h: "h-[78px]", text: "text-sm", suit: "text-base" },
  lg: { w: "w-[72px]", h: "h-[100px]", text: "text-base", suit: "text-lg" },
} as const;

interface Props {
  card: PlayingCardType | null;
  size?: "sm" | "md" | "lg";
}

export default function PlayingCard({ card, size = "md" }: Props) {
  const s = SIZES[size];

  if (!card) {
    return (
      <div
        className={`${s.w} ${s.h} rounded-md bg-ndai-700 border border-ndai-800 flex items-center justify-center shadow-md`}
      >
        <div className="grid grid-cols-2 gap-0.5 opacity-40">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className="text-white text-[8px]">{"\u2666"}</span>
          ))}
        </div>
      </div>
    );
  }

  const rank = RANK_NAMES[card.rank] ?? "?";
  const suitSymbol = SUIT_SYMBOLS[card.suit] ?? "?";
  const color = SUIT_COLORS[card.suit] ?? "text-black";

  return (
    <div
      className={`${s.w} ${s.h} rounded-md bg-white border border-gray-300 flex flex-col items-start p-1 shadow-md ${color}`}
    >
      <span className={`${s.text} font-bold leading-none`}>{rank}</span>
      <span className={`${s.suit} leading-none`}>{suitSymbol}</span>
      <span className={`${s.suit} leading-none mt-auto self-end`}>{suitSymbol}</span>
    </div>
  );
}
