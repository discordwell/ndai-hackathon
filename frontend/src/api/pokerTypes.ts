export interface PlayingCard {
  rank: number;  // 2-14
  suit: number;  // 0-3 (clubs, diamonds, hearts, spades)
}

export interface PokerTableSummary {
  id: string;
  small_blind: number;
  big_blind: number;
  min_buy_in: number;
  max_buy_in: number;
  max_seats: number;
  player_count: number;
  status: string;
  escrow_contract?: string;
}

export interface SeatView {
  seat_index: number;
  player_id: string;
  stack: number;
  is_active: boolean;
  is_sitting_out: boolean;
  current_bet: number;
  has_hole_cards: boolean;
  hole_cards: PlayingCard[] | null;
}

export interface PotView {
  amount: number;
  eligible_players: string[];
}

export interface TableView {
  table_id: string;
  small_blind: number;
  big_blind: number;
  min_buy_in: number;
  max_buy_in: number;
  max_seats: number;
  seats: (SeatView | null)[];
  hand_number: number | null;
  phase: string;
  dealer_seat: number | null;
  small_blind_seat?: number;
  big_blind_seat?: number;
  action_on: number | null;
  community_cards: PlayingCard[];
  pots: PotView[];
  current_bet?: number;
  min_raise?: number;
  escrow_contract: string;
}

export interface CreateTableRequest {
  small_blind: number;
  big_blind: number;
  min_buy_in: number;
  max_buy_in: number;
  max_seats: number;
  action_timeout_sec?: number;
}

export interface JoinTableRequest {
  buy_in: number;
  wallet_address: string;
  deposit_tx_hash?: string;
  preferred_seat?: number;
}

export interface PlayerActionRequest {
  action: "fold" | "check" | "call" | "bet" | "raise" | "all_in";
  amount?: number;
}

export interface GameEvent {
  type: string;
  data: Record<string, any>;
}
