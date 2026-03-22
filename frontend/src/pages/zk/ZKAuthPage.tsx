import React, { useState } from "react";
import { useZKAuth } from "../../contexts/ZKAuthContext";

export function ZKAuthPage() {
  const { login, isDerivingKey, isAuthenticated, publicKeyHex } = useZKAuth();
  const [passphrase, setPassphrase] = useState("");
  const [error, setError] = useState("");
  const [derived, setDerived] = useState(false);

  // If already authenticated, redirect
  if (isAuthenticated && !derived) {
    window.location.hash = "#/zk";
    return null;
  }

  async function handleDerive(e: React.FormEvent) {
    e.preventDefault();
    if (!passphrase.trim()) return;
    setError("");
    try {
      await login(passphrase);
      setDerived(true);
      // Brief pause to show the pubkey preview, then redirect
      setTimeout(() => {
        window.location.hash = "#/zk";
      }, 1200);
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    }
  }

  return (
    <div className="min-h-screen bg-void-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-void-800 border border-void-700 rounded-lg p-6">
          {/* Header */}
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-void-50 tracking-wider mb-1">
              0DAY
            </h1>
            <p className="text-xs text-void-400">
              Zero-Knowledge Vulnerability Marketplace
            </p>
          </div>

          {/* Derivation success preview */}
          {derived && publicKeyHex ? (
            <div className="text-center space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-2 bg-void-900 border border-void-600 rounded">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-xs font-mono text-void-200">
                  {publicKeyHex.slice(0, 16)}...
                </span>
              </div>
              <p className="text-xs text-void-400">
                Identity derived. Redirecting...
              </p>
            </div>
          ) : (
            <form onSubmit={handleDerive} className="space-y-4">
              {/* Passphrase input */}
              <div>
                <label className="block text-xs font-medium text-void-200 mb-1">
                  Passphrase
                </label>
                <input
                  type="password"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  placeholder="Enter your passphrase"
                  disabled={isDerivingKey}
                  className="w-full px-3 py-2 bg-void-900 border border-void-600 text-void-50 rounded text-sm focus:border-void-400 focus:outline-none disabled:opacity-50 placeholder:text-void-500"
                  autoFocus
                />
              </div>

              {/* Warning */}
              <p className="text-xs text-yellow-500/80 leading-relaxed">
                Your passphrase IS your identity. There is no recovery. The same
                passphrase always derives the same keypair.
              </p>

              {/* Error */}
              {error && (
                <div className="text-xs text-red-400 bg-red-900/30 border border-red-800 rounded px-3 py-2">
                  {error}
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={isDerivingKey || !passphrase.trim()}
                className="w-full py-2.5 bg-void-500 hover:bg-void-400 text-white rounded font-medium text-sm disabled:opacity-50 transition-colors"
              >
                {isDerivingKey ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg
                      className="animate-spin h-4 w-4"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    Deriving cryptographic identity...
                  </span>
                ) : (
                  "Derive Identity"
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
