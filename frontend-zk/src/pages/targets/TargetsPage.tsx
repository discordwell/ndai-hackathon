import React, { useState, useEffect } from "react";
import { getTargets } from "../../api/targets";
import type { KnownTarget } from "../../api/types";
import { TargetCard } from "../../components/targets/TargetCard";

export function TargetsPage() {
  const [targets, setTargets] = useState<KnownTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getTargets()
      .then(setTargets)
      .catch((e) => setError(e.detail || "Failed to load targets"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-3 border-zk-border border-t-zk-text animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-mono font-extrabold text-zk-text uppercase">Verification Targets</h1>
        <p className="text-xs text-zk-muted font-mono mt-1">
          Choose a target software to verify your 0day against.
        </p>
      </div>

      {error && (
        <div className="border-3 border-red-600 bg-red-50 p-4 text-red-700 text-sm font-mono mb-6">
          {error}
        </div>
      )}

      {targets.length === 0 ? (
        <div className="border-3 border-zk-border bg-white p-12 text-center">
          <p className="text-zk-muted text-sm font-mono">No verification targets available yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {targets.map((target) => (
            <TargetCard
              key={target.id}
              target={target}
              onClick={() => (window.location.hash = `#/targets/${target.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
