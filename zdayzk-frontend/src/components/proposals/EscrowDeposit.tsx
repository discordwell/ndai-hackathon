import React, { useState } from "react";
import { useWallet } from "../../contexts/WalletContext";

interface Props {
  requiredAmountEth: number;
  hasBadge: boolean;
  onDeposited: (txHash: string) => void;
}

export function EscrowDeposit({ requiredAmountEth, hasBadge, onDeposited }: Props) {
  const wallet = useWallet();
  const [status, setStatus] = useState<"idle" | "pending" | "confirmed" | "error">("idle");
  const [error, setError] = useState("");
  const [txHash, setTxHash] = useState("");

  if (hasBadge) {
    return (
      <div className="glass-card p-5">
        <div className="flex items-center gap-3">
          <span className="text-2xl">&#9889;</span>
          <div>
            <h3 className="text-sm font-semibold text-success-400">Badge holder — no deposit required</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Your verified seller badge exempts you from the escrow deposit.
            </p>
          </div>
        </div>
      </div>
    );
  }

  async function handleDeposit() {
    if (!wallet.isConnected) return;
    setStatus("pending");
    setError("");

    try {
      const { ethers } = await import("ethers");
      const provider = new ethers.BrowserProvider((window as any).ethereum);
      const signer = await provider.getSigner();

      // Send ETH to the deposit contract (placeholder address)
      const tx = await signer.sendTransaction({
        to: "0x0000000000000000000000000000000000000000", // Replaced by contract address
        value: ethers.parseEther(requiredAmountEth.toString()),
      });

      setTxHash(tx.hash);
      setStatus("pending");

      await tx.wait();
      setStatus("confirmed");
      onDeposited(tx.hash);
    } catch (err: any) {
      setError(err.message || "Transaction failed");
      setStatus("error");
    }
  }

  return (
    <div className="glass-card p-5 space-y-4">
      <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
        <span className="w-5 h-5 rounded bg-accent-400/10 text-accent-400 text-[10px] font-mono flex items-center justify-center">$</span>
        Escrow Deposit
      </h3>

      <div className="flex items-center justify-between bg-surface-800 rounded-lg px-4 py-3">
        <span className="text-xs text-gray-500">Required deposit</span>
        <span className="text-sm font-mono text-accent-400">{requiredAmountEth} ETH</span>
      </div>

      {error && (
        <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-3 rounded-lg">
          {error}
        </div>
      )}

      {txHash && (
        <div className="text-xs text-gray-500 font-mono break-all">
          TX: {txHash}
        </div>
      )}

      {status === "confirmed" ? (
        <div className="flex items-center gap-2 text-success-400 text-sm">
          <CheckCircleIcon />
          <span>Deposit confirmed</span>
        </div>
      ) : !wallet.isConnected ? (
        <button
          onClick={wallet.connect}
          className="w-full py-2.5 bg-surface-800 border border-accent-500/30 text-white font-medium rounded-lg hover:border-accent-400/60 hover:bg-surface-700 transition-colors text-sm"
        >
          Connect Wallet
        </button>
      ) : (
        <button
          onClick={handleDeposit}
          disabled={status === "pending"}
          className="w-full py-2.5 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 disabled:opacity-50 transition-colors text-sm"
        >
          {status === "pending" ? "Depositing..." : "Deposit"}
        </button>
      )}
    </div>
  );
}

function CheckCircleIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
