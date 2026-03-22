import React from "react";
import { useWallet } from "../../contexts/WalletContext";

export function ConnectWalletButton() {
  const { isConnected, address, isCorrectChain, connect, disconnect, switchToBaseSepolia } =
    useWallet();

  if (!isConnected) {
    return (
      <button
        onClick={connect}
        className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium border border-surface-600 rounded-lg text-gray-300 hover:border-accent-500/40 hover:text-white transition-all"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a2.25 2.25 0 00-2.25-2.25H15a3 3 0 110-6h.75A2.25 2.25 0 0018 6V4.5A2.25 2.25 0 0015.75 2.25h-9A2.25 2.25 0 004.5 4.5v15A2.25 2.25 0 006.75 21.75h9A2.25 2.25 0 0018 19.5V18a2.25 2.25 0 00-2.25-2.25H15a3 3 0 010-6h.75" />
        </svg>
        Connect Wallet
      </button>
    );
  }

  if (!isCorrectChain) {
    return (
      <button
        onClick={switchToBaseSepolia}
        className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-danger-500/20 border border-danger-500/40 rounded-lg text-danger-400 hover:bg-danger-500/30 transition-all"
      >
        Wrong Network
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-surface-800 border border-surface-700 rounded-lg text-gray-300">
        <span className="w-1.5 h-1.5 rounded-full bg-success-400" />
        {address!.slice(0, 6)}...{address!.slice(-4)}
      </span>
      <button
        onClick={disconnect}
        className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors"
        title="Disconnect"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
