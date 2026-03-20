interface Pot {
  amount: number;
  eligible_players: string[];
}

interface Props {
  pots: Pot[];
}

function formatAmount(amount: number): string {
  // If amount is large enough to be wei, convert to ETH
  if (amount >= 1e15) {
    const eth = amount / 1e18;
    return eth.toFixed(6).replace(/\.?0+$/, "") + " ETH";
  }
  return amount.toLocaleString();
}

export default function PotDisplay({ pots }: Props) {
  if (pots.length === 0) return null;

  return (
    <div className="flex flex-col items-center gap-1">
      {pots.map((pot, i) => (
        <div
          key={i}
          className="bg-black/60 rounded-full px-4 py-1 text-white text-sm font-semibold"
        >
          {i > 0 && <span className="text-gray-400 text-xs mr-1">Side Pot:</span>}
          {i === 0 && pots.length > 1 && <span className="text-gray-400 text-xs mr-1">Main:</span>}
          {formatAmount(pot.amount)}
        </div>
      ))}
    </div>
  );
}
