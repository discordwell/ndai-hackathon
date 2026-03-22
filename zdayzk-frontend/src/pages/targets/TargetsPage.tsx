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
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white">Verification Targets</h1>
        <p className="text-xs text-gray-500 mt-1">
          Choose a target software to verify your 0day against.
        </p>
      </div>

      {error && (
        <div className="glass-card p-4 border-danger-500/30 text-danger-400 text-sm mb-6">
          {error}
        </div>
      )}

      {targets.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-gray-400 text-sm">No verification targets available yet.</p>
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
