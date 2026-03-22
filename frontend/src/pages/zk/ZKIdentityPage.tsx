import React, { useState } from "react";
import { useZKAuth } from "../../contexts/ZKAuthContext";

export function ZKIdentityPage() {
  const { publicKeyHex, logout } = useZKAuth();
  const [copied, setCopied] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<{
    match: boolean;
    expected?: string;
    actual?: string;
    error?: string;
  } | null>(null);

  function copyPubkey() {
    if (!publicKeyHex) return;
    navigator.clipboard.writeText(publicKeyHex);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function handleDestroy() {
    logout();
    window.location.hash = "#/zk/auth";
  }

  async function handleVerifyBundle() {
    setVerifying(true);
    setVerifyResult(null);
    try {
      // 1. Fetch integrity manifest
      const manifestRes = await fetch("/assets/integrity.json");
      if (!manifestRes.ok) throw new Error("Could not fetch integrity.json");
      const manifest: Record<string, string> = await manifestRes.json();

      // 2. Find the current page's script tag
      const scripts = document.querySelectorAll("script[src]");
      let scriptSrc = "";
      for (const s of scripts) {
        const src = (s as HTMLScriptElement).src;
        if (src.includes("/assets/")) {
          scriptSrc = src;
          break;
        }
      }
      if (!scriptSrc) throw new Error("Could not locate bundle script tag");

      // Extract relative path from src
      const url = new URL(scriptSrc);
      const relativePath = url.pathname;

      // 3. Fetch the script content and compute SHA-256
      const scriptRes = await fetch(relativePath);
      if (!scriptRes.ok) throw new Error("Could not fetch bundle script");
      const scriptBytes = await scriptRes.arrayBuffer();
      const hashBuffer = await crypto.subtle.digest("SHA-256", scriptBytes);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const actualHash = hashArray
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");

      // 4. Look up expected hash
      const manifestKey = Object.keys(manifest).find((k) =>
        relativePath.endsWith(k)
      );
      const expectedHash = manifestKey ? manifest[manifestKey] : undefined;

      if (!expectedHash) {
        setVerifyResult({
          match: false,
          actual: actualHash,
          error: "Bundle not found in integrity manifest",
        });
      } else {
        setVerifyResult({
          match: actualHash === expectedHash,
          expected: expectedHash,
          actual: actualHash,
        });
      }
    } catch (err: any) {
      setVerifyResult({
        match: false,
        error: err.message || "Verification failed",
      });
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-bold text-void-50">Identity</h1>

      {/* Public Key */}
      <div className="bg-void-800 border border-void-700 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-void-50 mb-3">Public Key</h2>
        <div
          onClick={copyPubkey}
          className="bg-void-900 border border-void-600 rounded p-3 font-mono text-xs text-void-200 break-all cursor-pointer hover:border-void-400 transition-colors leading-relaxed"
          title="Click to copy"
        >
          {publicKeyHex || "No key loaded"}
        </div>
        <p className="text-[10px] text-void-500 mt-2">
          {copied ? (
            <span className="text-green-400">Copied to clipboard</span>
          ) : (
            "Click to copy"
          )}
        </p>
      </div>

      {/* Session Info */}
      <div className="bg-void-800 border border-void-700 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-void-50 mb-2">Session</h2>
        <p className="text-xs text-void-400 leading-relaxed">
          Token stored in sessionStorage — clears when tab closes. Private key
          held in memory only and never persisted.
        </p>
        <button
          onClick={handleDestroy}
          className="mt-3 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded text-xs font-medium transition-colors"
        >
          Destroy Session
        </button>
      </div>

      {/* JS Integrity Verification */}
      <div className="bg-void-800 border border-void-700 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-void-50 mb-2">
          JS Integrity Verification
        </h2>
        <p className="text-xs text-void-400 mb-3 leading-relaxed">
          Verify the loaded JavaScript bundle matches the expected SHA-256 hash
          from the integrity manifest.
        </p>

        <button
          onClick={handleVerifyBundle}
          disabled={verifying}
          className="px-4 py-2 bg-void-500 hover:bg-void-400 text-white rounded text-xs font-medium disabled:opacity-50 transition-colors"
        >
          {verifying ? "Verifying..." : "Verify Bundle"}
        </button>

        {verifyResult && (
          <div
            className={`mt-3 p-3 rounded border text-xs ${
              verifyResult.match
                ? "bg-green-900/20 border-green-500/30"
                : "bg-red-900/20 border-red-500/30"
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              {verifyResult.match ? (
                <>
                  <span className="text-green-400 text-base">&#10003;</span>
                  <span className="text-green-400 font-medium">
                    Integrity verified
                  </span>
                </>
              ) : (
                <>
                  <span className="text-red-400 text-base">&#10007;</span>
                  <span className="text-red-400 font-medium">
                    {verifyResult.error || "Hash mismatch"}
                  </span>
                </>
              )}
            </div>

            {verifyResult.actual && (
              <div className="space-y-1">
                <div>
                  <span className="text-void-400">Computed: </span>
                  <span className="font-mono text-void-200 break-all">
                    {verifyResult.actual}
                  </span>
                </div>
                {verifyResult.expected && (
                  <div>
                    <span className="text-void-400">Expected: </span>
                    <span className="font-mono text-void-200 break-all">
                      {verifyResult.expected}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
