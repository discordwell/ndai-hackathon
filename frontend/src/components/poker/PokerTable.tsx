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

function getSeatPositions(
  totalSeats: number,
  heroSeatIndex: number | null
): [number, number][] {
  const positions: [number, number][] = [];
  const heroOffset = heroSeatIndex !== null ? heroSeatIndex : 0;

  for (let i = 0; i < totalSeats; i++) {
    const seatIdx = (i + heroOffset) % totalSeats;
    const angle = (Math.PI / 2) + (i * 2 * Math.PI) / totalSeats;
    // Slightly wider ellipse for breathing room
    const left = 50 + 42 * Math.cos(angle);
    const top = 50 + 42 * Math.sin(angle);
    positions[seatIdx] = [left, top];
  }

  return positions;
}

export function PokerTable({ tableView, myPlayerId, onAction }: Props) {
  if (!tableView) {
    return (
      <div className="w-full h-full bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full border-2 border-gold-500/30 border-t-gold-400 animate-spin" />
          <span className="text-gray-500 text-sm tracking-wide">Loading table...</span>
        </div>
      </div>
    );
  }

  const heroSeatIndex = myPlayerId
    ? tableView.seats.findIndex((s) => s?.player_id === myPlayerId)
    : null;
  const heroIdx = heroSeatIndex !== null && heroSeatIndex >= 0 ? heroSeatIndex : null;

  const positions = getSeatPositions(tableView.max_seats, heroIdx);

  const heroSeat = heroIdx !== null ? tableView.seats[heroIdx] : null;
  const isHeroTurn = heroIdx !== null && tableView.action_on === heroIdx;

  const heroCurrentBet = heroSeat?.current_bet ?? 0;
  const tableCurrent = tableView.current_bet ?? 0;
  const callAmount = Math.max(0, tableCurrent - heroCurrentBet);
  const canCheck = callAmount === 0;
  const minRaise = tableView.min_raise ?? tableCurrent * 2;
  const maxRaise = heroSeat ? heroSeat.stack : 0;

  const phaseLabel: Record<string, string> = {
    waiting: "Waiting for players",
    preflop: "Pre-Flop",
    flop: "Flop",
    turn: "Turn",
    river: "River",
    showdown: "Showdown",
  };

  return (
    <div className="w-full h-full bg-gray-950 flex items-center justify-center p-4 overflow-hidden">
      {/* Ambient background glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[500px] bg-felt-800/20 rounded-full blur-[120px]" />
      </div>

      <div className="relative w-full max-w-5xl aspect-[16/10]">
        {/* Table outer rim (wood) */}
        <div
          className="absolute inset-[6%] rounded-[50%] shadow-2xl"
          style={{
            background: "linear-gradient(160deg, #4a3520 0%, #2a1f10 40%, #3d2b14 70%, #2a1f10 100%)",
            boxShadow: "0 0 60px rgba(0,0,0,0.6), inset 0 2px 4px rgba(255,255,255,0.05)",
          }}
        />

        {/* Table felt surface */}
        <div
          className="absolute inset-[8%] rounded-[50%] overflow-hidden"
          style={{
            background: "radial-gradient(ellipse at 40% 35%, #247a48 0%, #1e6b3e 30%, #1a5c36 60%, #144a2a 100%)",
            boxShadow: "inset 0 4px 30px rgba(0,0,0,0.4), inset 0 0 80px rgba(0,0,0,0.2)",
          }}
        >
          {/* Felt texture overlay */}
          <div
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg width='4' height='4' viewBox='0 0 4 4' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 3h1v1H1V3zm2-2h1v1H3V1z' fill='%23fff' fill-opacity='1'/%3E%3C/svg%3E")`,
            }}
          />

          {/* Rail line */}
          <div className="absolute inset-3 rounded-[50%] border border-white/[0.04]" />
        </div>

        {/* Phase indicator */}
        {tableView.phase && tableView.phase !== "waiting" && (
          <div className="absolute top-[15%] left-1/2 -translate-x-1/2 z-10">
            <span className="text-white/20 text-[10px] uppercase tracking-[0.2em] font-medium">
              {phaseLabel[tableView.phase] ?? tableView.phase}
              {tableView.hand_number ? ` \u00B7 Hand #${tableView.hand_number}` : ""}
            </span>
          </div>
        )}

        {/* Community cards & pot - centered */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 pointer-events-none z-10">
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
              className="absolute -translate-x-1/2 -translate-y-1/2 z-20"
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

        {/* TrustKit branding on felt */}
        <div className="absolute bottom-[20%] left-1/2 -translate-x-1/2 z-0 pointer-events-none">
          <span className="text-white/[0.04] text-lg font-bold tracking-[0.3em] uppercase select-none">
            TrustKit
          </span>
        </div>
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
