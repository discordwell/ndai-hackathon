import React, { useEffect, useState } from "react";
import { listMySecrets, listAvailableSecrets, SecretResponse } from "../../api/secrets";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";

interface Props {
  mode: "mine" | "browse";
}

export function SecretListPage({ mode }: Props) {
  const [secrets, setSecrets] = useState<SecretResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetch = mode === "mine" ? listMySecrets : listAvailableSecrets;
    fetch()
      .then(setSecrets)
      .catch((err: any) => setError(err.detail || err.message || "Failed to load secrets"))
      .finally(() => setLoading(false));
  }, [mode]);

  const title = mode === "mine" ? "My Secrets" : "Browse Available Secrets";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{title}</h1>
        {mode === "mine" && (
          <a
            href="#/recall/new"
            className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium"
          >
            Upload Secret
          </a>
        )}
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : secrets.length === 0 ? (
        <EmptyState
          title={mode === "mine" ? "No secrets uploaded yet" : "No secrets available"}
          description={mode === "mine" ? "Upload your first secret to get started" : "Check back later"}
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
          {secrets.map((secret) => (
            <div key={secret.id} className="bg-white rounded-xl border border-gray-100 p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{secret.name}</h3>
                  {secret.description && (
                    <p className="text-sm text-gray-500 mt-0.5">{secret.description}</p>
                  )}
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded-full font-medium ${
                    secret.status === "active"
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {secret.status}
                </span>
              </div>
              <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
                <span>Uses remaining: {secret.uses_remaining}</span>
                <span>Max uses: {secret.policy.max_uses}</span>
                {secret.policy.allowed_actions.length > 0 && (
                  <span>Actions: {secret.policy.allowed_actions.join(", ")}</span>
                )}
              </div>
              <div className="mt-4 flex gap-2">
                {!secret.is_owner && (
                  <a
                    href={`#/recall/${secret.id}/use`}
                    className="px-3 py-1.5 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-xs font-medium"
                  >
                    Use Secret
                  </a>
                )}
                {secret.is_owner && (
                  <a
                    href={`#/recall/${secret.id}/log`}
                    className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-xs font-medium"
                  >
                    View Access Log
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
