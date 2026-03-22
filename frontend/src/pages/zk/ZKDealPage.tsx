import React, { useState, useEffect } from "react";
import { useZKAuth } from "../../contexts/ZKAuthContext";
import {
  getAgreement,
  connectWallet,
  startNegotiation,
  type ZKAgreementResponse,
} from "../../api/zkVulns";
import { WalletConnect } from "../../components/zk/WalletConnect";

function truncatePubkey(key: string): string {
  if (!key || key.length < 16) return key || "";
  return `${key.slice(0, 8)}...${key.slice(-8)}`;
}

export function ZKDealPage({ dealId }: { dealId: string }) {
  const { publicKeyHex } = useZKAuth();
  const [agreement, setAgreement] = useState<ZKAgreementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [negotiating, setNegotiating] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    getAgreement(dealId)
      .then(setAgreement)
      .catch((e) => setError(e.message || "Failed to load agreement"))
      .finally(() => setLoading(false));
  }, [dealId]);

  function copyToClipboard(text: string, label: string) {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  }

  async function handleWalletConnect(address: string) {
    if (!agreement) return;
    try {
      const updated = await connectWallet(dealId, { eth_address: address });
      setAgreement(updated);
    } catch (err: any) {
      setError(err.message || "Failed to connect wallet");
    }
  }

  async function handleStartNegotiation() {
    setNegotiating(true);
    setError("");
    try {
      await startNegotiation(dealId);
      // Refresh agreement to get updated status
      const updated = await getAgreement(dealId);
      setAgreement(updated);
    } catch (err: any) {
      setError(err.message || "Failed to start negotiation");
    } finally {
      setNegotiating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-void-400" />
      </div>
    );
  }

  if (!agreement) {
    return <div className="text-void-400 text-sm">Agreement not found</div>;
  }

  const isBuyer = publicKeyHex === agreement.buyer_pubkey;
  const isSeller = publicKeyHex === agreement.seller_pubkey;
  const bothWalletsConnected =
    !!agreement.seller_eth_address && !!agreement.buyer_eth_address;

  const statusColors: Record<string, string> = {
    proposed: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    negotiating: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    completed: "bg-green-500/20 text-green-400 border-green-500/30",
  };

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-bold text-void-50">Deal</h1>

      {error && (
        <div className="text-xs text-red-400 bg-red-900/30 border border-red-800 rounded px-3 py-2">
          {error}
        </div>
      )}

      {/* Status + Info card */}
      <div className="bg-void-800 border border-void-700 rounded-lg p-5">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-xs text-void-400">Status</span>
            <div className="mt-1">
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded border ${
                  statusColors[agreement.status] ||
                  "bg-void-700 text-void-300 border-void-600"
                }`}
              >
                {agreement.status}
              </span>
            </div>
          </div>
          <div>
            <span className="text-xs text-void-400">Vulnerability</span>
            <p className="font-mono text-xs text-void-200 mt-1">
              {agreement.vulnerability_id.slice(0, 16)}...
            </p>
          </div>
          <div>
            <span className="text-xs text-void-400">Seller</span>
            <button
              onClick={() =>
                copyToClipboard(agreement.seller_pubkey, "seller")
              }
              className="block font-mono text-xs text-void-200 mt-1 hover:text-void-50 transition-colors"
              title="Click to copy full pubkey"
            >
              {truncatePubkey(agreement.seller_pubkey)}
              {copied === "seller" && (
                <span className="ml-1 text-green-400">copied</span>
              )}
            </button>
          </div>
          <div>
            <span className="text-xs text-void-400">Buyer</span>
            <button
              onClick={() =>
                copyToClipboard(agreement.buyer_pubkey, "buyer")
              }
              className="block font-mono text-xs text-void-200 mt-1 hover:text-void-50 transition-colors"
              title="Click to copy full pubkey"
            >
              {truncatePubkey(agreement.buyer_pubkey)}
              {copied === "buyer" && (
                <span className="ml-1 text-green-400">copied</span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Wallet Connect section */}
      <div className="bg-void-800 border border-void-700 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-void-50 mb-3">
          Wallet Connection
        </h2>

        <div className="space-y-3">
          {/* Seller wallet */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-void-400">Seller Wallet</span>
            {agreement.seller_eth_address ? (
              <span className="flex items-center gap-1.5 text-xs font-mono text-void-200">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                {agreement.seller_eth_address.slice(0, 6)}...
                {agreement.seller_eth_address.slice(-4)}
              </span>
            ) : isSeller ? (
              <WalletConnect onConnect={handleWalletConnect} />
            ) : (
              <span className="text-xs text-void-500">Not connected</span>
            )}
          </div>

          {/* Buyer wallet */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-void-400">Buyer Wallet</span>
            {agreement.buyer_eth_address ? (
              <span className="flex items-center gap-1.5 text-xs font-mono text-void-200">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                {agreement.buyer_eth_address.slice(0, 6)}...
                {agreement.buyer_eth_address.slice(-4)}
              </span>
            ) : isBuyer ? (
              <WalletConnect onConnect={handleWalletConnect} />
            ) : (
              <span className="text-xs text-void-500">Not connected</span>
            )}
          </div>
        </div>
      </div>

      {/* Escrow section */}
      {bothWalletsConnected && (
        <div className="bg-void-800 border border-void-700 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-void-50 mb-3">Escrow</h2>

          {agreement.escrow_address ? (
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              <span className="text-xs font-mono text-void-200">
                {agreement.escrow_address}
              </span>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-void-400">
                Both wallets connected. Fund escrow to proceed.
              </p>
              <button className="px-4 py-2 bg-void-500 hover:bg-void-400 text-white rounded text-xs font-medium transition-colors">
                Fund Escrow
              </button>
            </div>
          )}
        </div>
      )}

      {/* Negotiation section */}
      {agreement.status === "proposed" && bothWalletsConnected && (
        <div className="bg-void-800 border border-void-700 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-void-50 mb-3">
            Negotiation
          </h2>
          <p className="text-xs text-void-400 mb-3">
            Both wallets connected. Start TEE-mediated negotiation.
          </p>
          <button
            onClick={handleStartNegotiation}
            disabled={negotiating}
            className="w-full py-2 bg-void-500 hover:bg-void-400 text-white rounded text-sm font-medium disabled:opacity-50 transition-colors"
          >
            {negotiating ? "Starting..." : "Start Negotiation"}
          </button>
        </div>
      )}

      {agreement.status === "negotiating" && (
        <div className="bg-void-800 border border-blue-500/30 rounded-lg p-5">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400" />
            <span className="text-xs text-blue-400 font-medium">
              Negotiation in progress...
            </span>
          </div>
        </div>
      )}

      {agreement.status === "completed" && (
        <div className="bg-void-800 border border-green-500/30 rounded-lg p-5">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-xs text-green-400 font-medium">
              Deal completed
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
