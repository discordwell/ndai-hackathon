import React, { useState } from "react";
import { createConversation } from "../../api/messaging";

export function NewConversationPage() {
  const [pubkey, setPubkey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleStart() {
    const trimmed = pubkey.trim();
    if (!trimmed || trimmed.length !== 64 || !/^[0-9a-f]{64}$/i.test(trimmed)) {
      setError("Enter a valid 64-character hex public key");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const conv = await createConversation({ peer_pubkey: trimmed });
      window.location.hash = `#/messages/${conv.id}`;
    } catch (err: any) {
      setError(err.detail || "Failed to create conversation");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto">
      <a href="#/messages" className="text-xs text-gray-500 hover:text-gray-300 transition-colors mb-4 inline-block">
        &larr; Back to Messages
      </a>

      <h1 className="text-xl font-bold text-white mb-2">New Message</h1>
      <p className="text-xs text-gray-500 mb-6">
        Enter the recipient's public key to start an encrypted conversation.
      </p>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-xs p-3 rounded-lg mb-4">
          {error}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-[11px] text-gray-500 mb-1.5">Recipient Public Key</label>
          <input
            value={pubkey}
            onChange={(e) => setPubkey(e.target.value)}
            placeholder="64-character hex Ed25519 public key"
            className="w-full px-3 py-2.5 bg-void-800 border border-void-700 rounded-lg text-sm font-mono text-white outline-none focus:border-accent-500/40 transition-colors"
          />
        </div>

        <button
          onClick={handleStart}
          disabled={loading || !pubkey.trim()}
          className="w-full py-2.5 bg-accent-500/20 border border-accent-500/30 text-accent-400 rounded-lg font-medium text-sm hover:bg-accent-500/30 disabled:opacity-50 transition-all"
        >
          {loading ? "Creating..." : "Start Encrypted Conversation"}
        </button>
      </div>

      <div className="mt-6 p-3 bg-void-800/50 rounded-lg border border-void-700/30">
        <p className="text-[11px] text-gray-500 leading-relaxed">
          Messages are encrypted with the Signal protocol (X3DH + Double Ratchet).
          The server stores only ciphertext — it cannot read your messages.
          Each message uses a unique key. Compromising one key does not reveal past messages.
        </p>
      </div>
    </div>
  );
}
