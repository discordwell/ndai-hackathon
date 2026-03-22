import type { PlayingCard as PlayingCardType } from "../../api/pokerTypes";
import PlayingCard from "./PlayingCard";

interface Props {
  cards: PlayingCardType[];
}

export default function CommunityCards({ cards }: Props) {
  return (
    <div className="flex gap-2.5 justify-center">
      {Array.from({ length: 5 }, (_, i) => {
        const card = cards[i];
        return card ? (
          <div
            key={i}
            className="animate-[fadeSlideUp_0.3s_ease-out]"
            style={{ animationDelay: `${i * 80}ms`, animationFillMode: "backwards" }}
          >
            <PlayingCard card={card} size="md" />
          </div>
        ) : (
          <div
            key={i}
            className="rounded-lg border border-white/5 bg-white/[0.02]"
            style={{ width: 58, height: 82 }}
          />
        );
      })}
    </div>
  );
}
