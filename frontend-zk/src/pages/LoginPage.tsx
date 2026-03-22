import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";

export function LoginPage() {
  const { login, isDerivingKey } = useAuth();
  const [passphrase, setPassphrase] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await login(passphrase);
      window.location.hash = "#/browse";
    } catch (err: any) {
      setError(err.detail || err.message || "Authentication failed");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <a href="#/" className="font-mono font-extrabold text-2xl tracking-tighter no-underline text-zk-text block mb-8">
          ZDAYZK
        </a>

        <h2 className="font-mono text-label mb-6">LOGIN</h2>

        {error && (
          <div className="border-2 border-zk-danger p-3 mb-4 font-mono text-sm text-zk-danger">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="zk-label">PASSPHRASE</label>
            <input
              type="password"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              className="zk-input"
              required
              placeholder="Enter your passphrase"
              disabled={isDerivingKey}
            />
          </div>
          <button type="submit" disabled={isDerivingKey} className="zk-btn-accent w-full disabled:opacity-50">
            {isDerivingKey ? "DERIVING KEY..." : "ENTER"}
          </button>
        </form>

        {isDerivingKey && (
          <p className="font-mono text-xs text-zk-muted mt-4">
            Deriving cryptographic identity (2-4 seconds)...
          </p>
        )}

        <p className="font-mono text-xs text-zk-muted mt-6">
          No identity? <a href="#/register">Create one</a>
        </p>
      </div>
    </div>
  );
}
