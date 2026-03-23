import React, { useState } from "react";
import { createSecret } from "../../api/secrets";

export function SecretCreatePage() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [actions, setActions] = useState<string[]>([]);
  const [actionInput, setActionInput] = useState("");
  const [maxUses, setMaxUses] = useState("10");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function addAction() {
    const trimmed = actionInput.trim();
    if (trimmed && !actions.includes(trimmed)) {
      setActions([...actions, trimmed]);
      setActionInput("");
    }
  }

  function removeAction(action: string) {
    setActions(actions.filter((a) => a !== action));
  }

  function handleActionKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      addAction();
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (actions.length === 0) {
      setError("Add at least one allowed action");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await createSecret({
        name,
        description: description || undefined,
        secret_value: secretValue,
        policy: {
          allowed_actions: actions,
          max_uses: parseInt(maxUses, 10),
        },
      });
      window.location.hash = "#/recall";
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to create secret");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <a href="#/recall" className="text-sm text-ndai-600 hover:underline">
          &larr; Back to My Secrets
        </a>
        <h1 className="text-2xl font-bold mt-2">Upload Secret</h1>
        <p className="text-sm text-gray-500 mt-1">
          Store a credential inside the TEE with policy-gated access
        </p>
      </div>
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        {error && (
          <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-4">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. AWS Production Keys"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this secret used for?"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Secret Value</label>
            <input
              type="password"
              required
              value={secretValue}
              onChange={(e) => setSecretValue(e.target.value)}
              placeholder="The credential or secret to store"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">
              Encrypted with AES-256-GCM before storage. Only decrypted inside the TEE during approved use.
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Allowed Actions</label>
            {actions.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {actions.map((a) => (
                  <span
                    key={a}
                    className="inline-flex items-center gap-1 bg-ndai-50 text-ndai-700 border border-ndai-200 rounded-full px-3 py-1 text-sm"
                  >
                    {a}
                    <button
                      type="button"
                      onClick={() => removeAction(a)}
                      className="text-ndai-400 hover:text-ndai-700 ml-0.5"
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <input
                type="text"
                value={actionInput}
                onChange={(e) => setActionInput(e.target.value)}
                onKeyDown={handleActionKeyDown}
                placeholder="e.g. list S3 buckets"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm"
              />
              <button
                type="button"
                onClick={addAction}
                disabled={!actionInput.trim()}
                className="px-3 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 text-sm font-medium"
              >
                Add
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Requests for unlisted actions are denied without consuming a use.
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Uses</label>
            <input
              type="number"
              required
              min="1"
              value={maxUses}
              onChange={(e) => setMaxUses(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">
              Secret auto-depletes after this many approved uses.
            </p>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm"
            >
              {submitting ? "Encrypting & Uploading..." : "Upload Secret"}
            </button>
            <a
              href="#/recall"
              className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm"
            >
              Cancel
            </a>
          </div>
        </form>
      </div>
    </div>
  );
}
