import React, { useEffect, useState } from "react";
import { getSecret, useSecret, SecretResponse, SecretUseResponse } from "../../api/secrets";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";

interface Props {
  id: string;
}

export function SecretUsePage({ id }: Props) {
  const [secret, setSecret] = useState<SecretResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SecretUseResponse | null>(null);
  const [useError, setUseError] = useState("");

  useEffect(() => {
    getSecret(id)
      .then(setSecret)
      .catch((err: any) => setError(err.detail || err.message || "Failed to load secret"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleUse(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setUseError("");
    setResult(null);
    try {
      const res = await useSecret(id, action);
      setResult(res);
    } catch (err: any) {
      setUseError(err.detail || err.message || "Failed to use secret");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!secret) return null;

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <a href="#/recall/browse" className="text-sm text-ndai-600 hover:underline">
          &larr; Back to Browse
        </a>
        <h1 className="text-2xl font-bold mt-2">{secret.name}</h1>
        {secret.description && (
          <p className="text-gray-500 mt-1">{secret.description}</p>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 mb-6">
        <h2 className="font-semibold text-gray-900 mb-3">Policy</h2>
        <div className="space-y-2 text-sm text-gray-700">
          <div className="flex justify-between">
            <span className="text-gray-500">Status</span>
            <span
              className={`font-medium ${secret.status === "active" ? "text-green-600" : "text-gray-600"}`}
            >
              {secret.status}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Uses remaining</span>
            <span className="font-medium">{secret.uses_remaining}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Allowed actions</span>
            <span className="font-medium">
              {secret.policy.allowed_actions.length > 0
                ? secret.policy.allowed_actions.join(", ")
                : "any"}
            </span>
          </div>
        </div>
      </div>

      {result ? (
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Result</h2>
          <div
            className={`p-3 rounded-lg text-sm mb-3 ${
              result.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-700"
            }`}
          >
            {result.success ? "Success" : "Failed"}
          </div>
          <div className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-3">
            {result.result}
          </div>
          {result.attestation_available && (
            <p className="mt-3 text-xs text-gray-500">
              Attestation available — this result was produced inside a TEE.
            </p>
          )}
          <button
            onClick={() => { setResult(null); setAction(""); }}
            className="mt-4 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm"
          >
            Use Again
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Request Access</h2>
          {useError && (
            <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-4">{useError}</div>
          )}
          <form onSubmit={handleUse} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Action</label>
              <textarea
                required
                value={action}
                onChange={(e) => setAction(e.target.value)}
                rows={4}
                placeholder={
                  secret.policy.allowed_actions.length > 0
                    ? `Allowed: ${secret.policy.allowed_actions.join(", ")}`
                    : "Describe what you want to do with this secret"
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm resize-none"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm"
            >
              {submitting ? "Requesting..." : "Request Access"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
