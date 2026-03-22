import React, { useState } from "react";

interface Props {
  requiredAmountEth: number;
  hasBadge: boolean;
  onDeposited: (txHash: string) => void;
}

export function EscrowDeposit({ requiredAmountEth, hasBadge, onDeposited }: Props) {
  const [txHash, setTxHash] = useState("");
  const [error, setError] = useState("");

  if (hasBadge) {
    return (
      <div className="border-3 border-emerald-600 bg-emerald-50 p-5">
        <h3 className="text-sm font-mono font-bold text-emerald-700 uppercase">
          Badge holder — no deposit required
        </h3>
        <p className="text-xs text-emerald-600 mt-1 font-mono">
          Your verified seller badge exempts you from the escrow deposit.
        </p>
      </div>
    );
  }

  function handleSubmit() {
    const trimmed = txHash.trim();
    if (!/^0x[a-fA-F0-9]{64}$/.test(trimmed)) {
      setError("Enter a valid transaction hash (0x + 64 hex chars)");
      return;
    }
    setError("");
    onDeposited(trimmed);
  }

  return (
    <div className="border-3 border-zk-border bg-white p-5 space-y-4">
      <h3 className="text-sm font-mono font-bold text-zk-text uppercase">
        Escrow Deposit
      </h3>

      <div className="flex items-center justify-between bg-zk-bg px-4 py-3 border-2 border-zk-border">
        <span className="text-xs text-zk-muted font-mono">Required deposit</span>
        <span className="text-sm font-mono font-bold text-zk-accent">{requiredAmountEth.toFixed(4)} ETH</span>
      </div>

      <p className="text-xs text-zk-muted font-mono">
        Send the deposit to the escrow contract, then paste the transaction hash below.
      </p>

      <input
        type="text"
        value={txHash}
        onChange={(e) => setTxHash(e.target.value)}
        placeholder="0x..."
        className="w-full px-3 py-2 bg-white border-2 border-zk-border text-sm text-zk-text font-mono outline-none focus:border-zk-accent"
      />

      {error && (
        <div className="text-red-600 text-xs font-mono font-bold">{error}</div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!txHash.trim()}
        className="w-full py-2.5 bg-zk-text text-white font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-accent disabled:opacity-50 transition-colors"
      >
        Confirm Deposit
      </button>
    </div>
  );
}
