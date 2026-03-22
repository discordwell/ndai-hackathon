import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";

export function RegisterPage() {
  const { register, isDerivingKey } = useAuth();
  const [passphrase, setPassphrase] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [publicKeyHex, setPublicKeyHex] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (passphrase !== confirm) {
      setError("Passphrases do not match");
      return;
    }

    try {
      const pubkey = await register(passphrase);
      setPublicKeyHex(pubkey);
    } catch (err: any) {
      setError(err.detail || err.message || "Registration failed");
    }
  }

  // After successful registration, show public key and link to marketplace
  if (publicKeyHex) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <a href="#/" className="font-mono font-extrabold text-2xl tracking-tighter no-underline text-zk-text block mb-8">
            ZDAYZK
          </a>

          <h2 className="font-mono text-label mb-6">IDENTITY CREATED</h2>

          <div className="border-2 border-zk-accent p-4 mb-6">
            <label className="zk-label mb-2 block">YOUR PUBLIC KEY</label>
            <p className="font-mono text-xs break-all text-zk-text">{publicKeyHex}</p>
          </div>

          <p className="font-mono text-xs text-zk-muted mb-6">
            Your passphrase is your identity. There is no recovery — remember it.
          </p>

          <a href="#/browse" className="zk-btn-accent w-full no-underline block text-center">
            ENTER MARKETPLACE
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <a href="#/" className="font-mono font-extrabold text-2xl tracking-tighter no-underline text-zk-text block mb-8">
          ZDAYZK
        </a>

        <h2 className="font-mono text-label mb-6">CREATE IDENTITY</h2>

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
              placeholder="Choose a strong passphrase"
              disabled={isDerivingKey}
            />
          </div>
          <div>
            <label className="zk-label">CONFIRM PASSPHRASE</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="zk-input"
              required
              placeholder="Repeat your passphrase"
              disabled={isDerivingKey}
            />
          </div>
          <button type="submit" disabled={isDerivingKey} className="zk-btn-accent w-full disabled:opacity-50">
            {isDerivingKey ? "DERIVING KEY..." : "CREATE IDENTITY"}
          </button>
        </form>

        {isDerivingKey && (
          <p className="font-mono text-xs text-zk-muted mt-4">
            Deriving cryptographic identity (2-4 seconds)...
          </p>
        )}

        <p className="font-mono text-xs text-zk-muted mt-6">
          Already have an identity? <a href="#/login">Login</a>
        </p>
      </div>
    </div>
  );
}
