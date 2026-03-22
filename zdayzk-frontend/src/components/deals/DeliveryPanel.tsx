import React, { useState } from "react";
import { downloadPayload, downloadKey } from "../../api/delivery";

interface Props {
  agreementId: string;
  isAccepted: boolean;
}

export function DeliveryPanel({ agreementId, isAccepted }: Props) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function handleDownload(type: "payload" | "key") {
    setDownloading(type);
    setError("");
    try {
      const blob = type === "payload"
        ? await downloadPayload(agreementId)
        : await downloadKey(agreementId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = type === "payload" ? `exploit_${agreementId.slice(0, 8)}.enc` : `key_${agreementId.slice(0, 8)}.enc`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.detail || `Failed to download ${type}`);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="glass-card p-6">
      <h3 className="text-sm font-semibold text-gray-300 mb-2">Sealed Delivery</h3>

      {!isAccepted ? (
        <p className="text-xs text-gray-500">
          Deal must be accepted on-chain before delivery is available.
        </p>
      ) : (
        <>
          <p className="text-xs text-gray-500 mb-4">
            Download the encrypted exploit and delivery key. Decrypt locally with your private key.
          </p>

          {error && (
            <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-2 rounded mb-3">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => handleDownload("payload")}
              disabled={downloading !== null}
              className="flex items-center gap-2 px-4 py-2 bg-accent-400/10 border border-accent-400/30 text-accent-400 rounded-lg text-xs font-medium hover:bg-accent-400/20 disabled:opacity-50 transition-all"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              {downloading === "payload" ? "Downloading..." : "Encrypted Exploit"}
            </button>
            <button
              onClick={() => handleDownload("key")}
              disabled={downloading !== null}
              className="flex items-center gap-2 px-4 py-2 bg-surface-700/50 border border-surface-600 text-gray-300 rounded-lg text-xs font-medium hover:border-surface-500 disabled:opacity-50 transition-all"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
              </svg>
              {downloading === "key" ? "Downloading..." : "Delivery Key"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
