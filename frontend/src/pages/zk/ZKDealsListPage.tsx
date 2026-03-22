import React, { useState, useEffect } from "react";
import { useZKAuth } from "../../contexts/ZKAuthContext";
import {
  listMyAgreements,
  type ZKAgreementResponse,
} from "../../api/zkVulns";

function truncatePubkey(key: string): string {
  if (!key || key.length < 16) return key || "";
  return `${key.slice(0, 8)}...${key.slice(-8)}`;
}

const STATUS_COLORS: Record<string, string> = {
  proposed: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  negotiating: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  completed: "bg-green-500/20 text-green-400 border-green-500/30",
};

export function ZKDealsListPage() {
  const { publicKeyHex } = useZKAuth();
  const [agreements, setAgreements] = useState<ZKAgreementResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listMyAgreements()
      .then(setAgreements)
      .catch((e) => setError(e.message || "Failed to load deals"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-bold text-void-50 mb-4">My Deals</h1>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-void-400" />
        </div>
      ) : error ? (
        <div className="text-red-400 text-sm">{error}</div>
      ) : agreements.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-void-400 text-sm mb-3">No deals yet.</p>
          <a
            href="#/zk"
            className="px-4 py-2 bg-void-500 hover:bg-void-400 text-white rounded text-sm font-medium transition-colors"
          >
            Browse Marketplace
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {agreements.map((a) => {
            const counterparty =
              publicKeyHex === a.buyer_pubkey
                ? a.seller_pubkey
                : a.buyer_pubkey;
            const role =
              publicKeyHex === a.buyer_pubkey ? "Buyer" : "Seller";

            return (
              <a
                key={a.id}
                href={`#/zk/deals/${a.id}`}
                className="bg-void-800 border border-void-700 hover:border-void-500 rounded-lg p-4 transition-all block"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs text-void-400">{role}</span>
                  <span
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${
                      STATUS_COLORS[a.status] ||
                      "bg-void-700 text-void-300 border-void-600"
                    }`}
                  >
                    {a.status}
                  </span>
                </div>

                <div className="mb-2">
                  <span className="text-xs text-void-400">Counterparty</span>
                  <p className="font-mono text-xs text-void-200 mt-0.5">
                    {truncatePubkey(counterparty)}
                  </p>
                </div>

                <div>
                  <span className="text-xs text-void-400">Vulnerability</span>
                  <p className="font-mono text-xs text-void-200 mt-0.5">
                    {a.vulnerability_id.slice(0, 16)}...
                  </p>
                </div>

                <div className="mt-3 pt-2 border-t border-void-700">
                  <span className="text-[10px] text-void-500">
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
