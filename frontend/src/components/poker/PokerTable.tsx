import type { TableView } from "../../api/pokerTypes";
import PlayerSeat from "./PlayerSeat";
import CommunityCards from "./CommunityCards";
import PotDisplay from "./PotDisplay";
import BettingControls from "./BettingControls";

interface Props {
  tableView: TableView | null;
  myPlayerId: string | null;
  onAction: (action: string, amount?: number) => void;
}

/**
 * Compute seat positions around an ellipse.
 * Returns [left%, top%] for each seat, with the hero rotated to the bottom.
 */
function getSeatPositions(
  totalSeats: number,
  heroSeatIndex: number | null
): [number, number][] {
  const positions: [number, number][] = [];
  const heroOffset = heroSeatIndex !== null ? heroSeatIndex : 0;

  for (let i = 0; i < totalSeats; i++) {
    // Rotate so hero is at the bottom (angle = PI/2 = bottom of ellipse)
    const seatIdx = (i + heroOffset) % totalSeats;
    const angle = (Math.PI / 2) + (i * 2 * Math.PI) / totalSeats;
    const left = 50 + 40 * Math.cos(angle);
    const top = 50 + 40 * Math.sin(angle);
    positions[seatIdx] = [left, top];
  }

  return positions;
}

export function PokerTable({ tableView, myPlayerId, onAction }: Props) {
  if (!tableView) {
    return (
      <div className="w-full h-full bg-gray-950 flex items-center justify-center">
        <span className="text-gray-500 text-lg">No table data</span>
      </div>
    );
  }

  const heroSeatIndex = myPlayerId
    ? tableView.seats.findIndex((s) => s?.player_id === myPlayerId)
    : null;
  const heroIdx = heroSeatIndex !== null && heroSeatIndex >= 0 ? heroSeatIndex : null;

  const positions = getSeatPositions(tableView.max_seats, heroIdx);

  const heroSeat = heroIdx !== null ? tableView.seats[heroIdx] : null;
  const isHeroTurn =
    heroIdx !== null && tableView.action_on === heroIdx;

  // Determine call/raise info for betting controls
  const heroCurrentBet = heroSeat?.current_bet ?? 0;
  const tableCurrent = tableView.current_bet ?? 0;
  const callAmount = Math.max(0, tableCurrent - heroCurrentBet);
  const canCheck = callAmount === 0;
  const minRaise = tableView.min_raise ?? tableCurrent * 2;
  const maxRaise = heroSeat ? heroSeat.stack + heroCurrentBet : 0;

  return (
    <div className="w-full h-full bg-gray-950 flex items-center justify-center p-4">
      <div className="relative w-full max-w-4xl aspect-[16/10]">
        {/* Table surface */}
        <div className="absolute inset-[10%] rounded-[50%] bg-gradient-to-b from-felt-600 to-felt-700 border-4 border-felt-500 shadow-2xl" />

        {/* Community cards & pot - centered */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 pointer-events-none">
          <PotDisplay pots={tableView.pots} />
          <CommunityCards cards={tableView.community_cards} />
        </div>

        {/* Player seats */}
        {tableView.seats.map((seat, i) => {
          const pos = positions[i];
          if (!pos) return null;

          return (
            <div
              key={i}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${pos[0]}%`, top: `${pos[1]}%` }}
            >
              <PlayerSeat
                seat={seat}
                isHero={i === heroIdx}
                isDealer={tableView.dealer_seat === i}
                isSmallBlind={tableView.small_blind_seat === i}
                isBigBlind={tableView.big_blind_seat === i}
                isActionOn={tableView.action_on === i}
              />
            </div>
          );
        })}
      </div>

      {/* Betting controls */}
      {isHeroTurn && (
        <BettingControls
          callAmount={callAmount}
          minRaise={minRaise}
          maxRaise={maxRaise}
          canCheck={canCheck}
          onAction={onAction}
          disabled={false}
        />
      )}
    </div>
  );
}
