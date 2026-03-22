import React, { useState } from "react";
import { BrowserProvider } from "ethers";

interface WalletConnectProps {
  onConnect: (address: string) => void;
  connectedAddress?: string;
}

export function WalletConnect({
  onConnect,
  connectedAddress,
}: WalletConnectProps) {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");

  if (connectedAddress) {
    return (
      <span className="flex items-center gap-1.5 text-xs font-mono text-void-200">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
        {connectedAddress.slice(0, 6)}...{connectedAddress.slice(-4)}
      </span>
    );
  }

  async function handleConnect() {
    setConnecting(true);
    setError("");

    try {
      if (!(window as any).ethereum) {
        throw new Error("MetaMask not detected. Install MetaMask to continue.");
      }

      const provider = new BrowserProvider((window as any).ethereum);
      const accounts = await provider.send("eth_requestAccounts", []);

      if (!accounts || accounts.length === 0) {
        throw new Error("No accounts returned");
      }

      onConnect(accounts[0]);
    } catch (err: any) {
      if (err.code === 4001) {
        setError("Connection rejected");
      } else {
        setError(err.message || "Failed to connect wallet");
      }
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {error && (
        <span className="text-[10px] text-red-400 max-w-[160px] truncate">
          {error}
        </span>
      )}
      <button
        onClick={handleConnect}
        disabled={connecting}
        className="px-3 py-1.5 bg-void-600 hover:bg-void-500 text-void-50 rounded text-xs font-medium disabled:opacity-50 transition-colors"
      >
        {connecting ? "Connecting..." : "Connect MetaMask"}
      </button>
    </div>
  );
}
