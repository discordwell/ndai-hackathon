interface Pot {
  amount: number;
  eligible_players: string[];
}

interface Props {
  pots: Pot[];
}

function formatAmount(amount: number): string {
  if (amount >= 1e15) {
    const eth = amount / 1e18;
    return eth.toFixed(4).replace(/\.?0+$/, "") + " ETH";
  }
  if (amount >= 1_000_000) return (amount / 1_000_000).toFixed(1) + "M";
  if (amount >= 10_000) return (amount / 1_000).toFixed(1) + "K";
  return amount.toLocaleString();
}

function ChipStack() {
  return (
    <div className="flex flex-col items-center -space-y-1.5">
      <div className="w-5 h-2.5 rounded-full bg-gradient-to-r from-red-500 to-red-600 border border-red-400/50 shadow-sm" />
      <div className="w-5 h-2.5 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 border border-blue-400/50 shadow-sm" />
      <div className="w-5 h-2.5 rounded-full bg-gradient-to-r from-green-500 to-green-600 border border-green-400/50 shadow-sm" />
    </div>
  );
}

export default function PotDisplay({ pots }: Props) {
  const total = pots.reduce((sum, p) => sum + p.amount, 0);
  if (total === 0) return null;

  return (
    <div className="flex flex-col items-center gap-1.5">
      {/* Main pot */}
      <div className="flex items-center gap-2.5 bg-black/50 backdrop-blur-sm rounded-full px-5 py-2 border border-white/10 shadow-lg">
        <ChipStack />
        <div className="flex flex-col">
          {pots.length > 1 && <span className="text-gray-500 text-[9px] uppercase tracking-wider">Main Pot</span>}
          <span className="text-white text-base font-bold tabular-nums tracking-tight">
            {formatAmount(pots[0]?.amount ?? total)}
          </span>
        </div>
      </div>

      {/* Side pots */}
      {pots.slice(1).map((pot, i) => (
        <div key={i} className="flex items-center gap-2 bg-black/40 backdrop-blur-sm rounded-full px-3.5 py-1 border border-white/5">
          <div className="w-3 h-3 rounded-full bg-gradient-to-b from-gold-400 to-gold-600 shadow-sm" />
          <span className="text-gray-400 text-xs font-medium tabular-nums">
            Side: {formatAmount(pot.amount)}
          </span>
        </div>
      ))}
    </div>
  );
}
