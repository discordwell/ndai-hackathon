import React, { useEffect, useState } from "react";
import { listMySecrets, listAvailableSecrets, revokeSecret, SecretResponse } from "../../api/secrets";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";

interface Props {
  mode: "mine" | "browse";
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return "bg-green-100 text-green-700";
    case "depleted":
      return "bg-amber-100 text-amber-700";
    case "revoked":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

function BrowseHero() {
  return (
    <div className="mb-8">
      <h1 className="text-2xl font-bold mb-2">Conditional Recall</h1>
      <p className="text-gray-500 mb-6">Secrets that think before they act</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="w-8 h-8 rounded-lg bg-ndai-50 flex items-center justify-center mb-3">
            <svg className="w-4 h-4 text-ndai-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h3 className="font-semibold text-gray-900 text-sm mb-1">Policy-Gated</h3>
          <p className="text-xs text-gray-500">Every access is validated against owner-defined constraints before execution</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="w-8 h-8 rounded-lg bg-ndai-50 flex items-center justify-center mb-3">
            <svg className="w-4 h-4 text-ndai-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h3 className="font-semibold text-gray-900 text-sm mb-1">TEE-Isolated</h3>
          <p className="text-xs text-gray-500">Secrets never leave the Trusted Execution Environment — not even the platform can see them</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <div className="w-8 h-8 rounded-lg bg-ndai-50 flex items-center justify-center mb-3">
            <svg className="w-4 h-4 text-ndai-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <h3 className="font-semibold text-gray-900 text-sm mb-1">Cryptographically Verified</h3>
          <p className="text-xs text-gray-500">SHA-256 hash chain proves every step of the session — tamper-evident by construction</p>
        </div>
      </div>
    </div>
  );
}

export function SecretListPage({ mode }: Props) {
  const [secrets, setSecrets] = useState<SecretResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revoking, setRevoking] = useState<string | null>(null);

  useEffect(() => {
    loadSecrets();
  }, [mode]);

  function loadSecrets() {
    setLoading(true);
    const fetch = mode === "mine" ? listMySecrets : listAvailableSecrets;
    fetch()
      .then(setSecrets)
      .catch((err: any) => setError(err.detail || err.message || "Failed to load secrets"))
      .finally(() => setLoading(false));
  }

  async function handleRevoke(secretId: string) {
    if (!confirm("Are you sure you want to revoke this secret? This cannot be undone.")) return;
    setRevoking(secretId);
    try {
      await revokeSecret(secretId);
      loadSecrets();
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to revoke secret");
    } finally {
      setRevoking(null);
    }
  }

  return (
    <div>
      {mode === "browse" ? (
        <BrowseHero />
      ) : (
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">My Secrets</h1>
            <p className="text-sm text-gray-500 mt-1">Encrypted at rest, accessible only through your policy</p>
          </div>
          <a
            href="#/recall/new"
            className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium"
          >
            Upload Secret
          </a>
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : secrets.length === 0 ? (
        <EmptyState
          title={mode === "mine" ? "No secrets uploaded yet" : "No secrets available"}
          description={
            mode === "mine"
              ? "Upload your first secret to see how TEE-gated conditional access works. Your secrets are encrypted at rest and can only be used through the policy you define."
              : "No secrets have been shared yet. When other users upload secrets with available uses, they will appear here for policy-gated access."
          }
          action={
            mode === "mine" ? (
              <a
                href="#/recall/new"
                className="inline-block px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium"
              >
                Upload Secret
              </a>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-4">
          {secrets.map((secret) => {
            const isDepleted = secret.status === "depleted";
            const isRevoked = secret.status === "revoked";
            const isInactive = isDepleted || isRevoked;
            return (
              <div
                key={secret.id}
                className={`bg-white rounded-xl border p-5 transition-opacity ${
                  isRevoked ? "border-red-200 opacity-60" :
                  isDepleted ? "border-gray-200 opacity-60" :
                  "border-gray-100"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className={`font-semibold ${isInactive ? "text-gray-500" : "text-gray-900"}`}>
                      {secret.name}
                    </h3>
                    {secret.description && (
                      <p className="text-sm text-gray-500 mt-0.5">{secret.description}</p>
                    )}
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusBadge(secret.status)}`}>
                    {secret.status}
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                  <span>Uses: {secret.uses_remaining}/{secret.policy.max_uses}</span>
                  {secret.policy.allowed_actions.length > 0 && (
                    <span>Actions: {secret.policy.allowed_actions.join(", ")}</span>
                  )}
                  <span>{timeAgo(secret.created_at)}</span>
                </div>
                <div className="mt-4 flex gap-2">
                  {!secret.is_owner && !isInactive && (
                    <a
                      href={`#/recall/${secret.id}/use`}
                      className="px-3 py-1.5 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-xs font-medium"
                    >
                      Use Secret
                    </a>
                  )}
                  {secret.is_owner && (
                    <>
                      <a
                        href={`#/recall/${secret.id}/log`}
                        className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-xs font-medium"
                      >
                        View Access Log
                      </a>
                      {secret.status === "active" && (
                        <button
                          onClick={() => handleRevoke(secret.id)}
                          disabled={revoking === secret.id}
                          className="px-3 py-1.5 border border-red-200 text-red-600 rounded-lg hover:bg-red-50 text-xs font-medium disabled:opacity-50"
                        >
                          {revoking === secret.id ? "Revoking..." : "Revoke"}
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
