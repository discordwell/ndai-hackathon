import type { PlayingCard as PlayingCardType } from "../../api/pokerTypes";
import PlayingCard from "./PlayingCard";

interface Props {
  cards: PlayingCardType[];
}

export default function CommunityCards({ cards }: Props) {
  const slots = Array.from({ length: 5 }, (_, i) => cards[i] ?? undefined);

  return (
    <div className="flex gap-2 justify-center">
      {slots.map((card, i) =>
        card ? (
          <PlayingCard key={i} card={card} size="md" />
        ) : (
          <div
            key={i}
            className="w-14 h-[78px] rounded-md border-2 border-dashed border-gray-600 bg-gray-800/30"
          />
        )
      )}
    </div>
  );
}
