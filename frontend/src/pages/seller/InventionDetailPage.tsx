import React, { useState, useEffect } from "react";
import { getInvention, deleteInvention } from "../../api/inventions";
import { Card } from "../../components/shared/Card";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { StatusBadge } from "../../components/shared/StatusBadge";
import type { InventionResponse } from "../../api/types";

function ValueBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{value.toFixed(2)}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full">
        <div
          className="h-2 bg-ndai-500 rounded-full transition-all"
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  );
}

export function InventionDetailPage({ id }: { id: string }) {
  const [invention, setInvention] = useState<InventionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const inv = await getInvention(id);
        setInvention(inv);
      } catch {
        setError("Invention not found");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleWithdraw() {
    if (!confirm("Withdraw this invention? It will no longer appear in the marketplace.")) return;
    setDeleting(true);
    try {
      await deleteInvention(id);
      window.location.hash = "#/seller/inventions";
    } catch (err: any) {
      setError(err.message || "Failed to withdraw");
      setDeleting(false);
    }
  }

  if (loading) return <LoadingSpinner />;
  if (!invention) return <div className="text-red-600">{error || "Not found"}</div>;

  return (
    <div className="max-w-3xl animate-fadeIn">
      <a
        href="#/seller/inventions"
        className="text-sm text-ndai-600 hover:text-ndai-700 mb-4 inline-block"
      >
        &larr; Back to inventions
      </a>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{invention.title}</h1>
          {invention.created_at && (
            <p className="text-xs text-gray-400 mt-1">
              Created {new Date(invention.created_at).toLocaleDateString()}
            </p>
          )}
        </div>
        <StatusBadge status={invention.status} />
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-4">{error}</div>
      )}

      {/* Summary & Category */}
      <Card className="mb-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Category</span>
            <div className="mt-1 font-medium">{invention.category || "—"}</div>
          </div>
          <div>
            <span className="text-gray-500">Development Stage</span>
            <div className="mt-1 font-medium capitalize">{invention.development_stage || "—"}</div>
          </div>
          <div>
            <span className="text-gray-500">Technical Domain</span>
            <div className="mt-1 font-medium">{invention.technical_domain || "—"}</div>
          </div>
        </div>
        {invention.anonymized_summary && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <span className="text-gray-500 text-sm">Anonymized Summary (visible to buyers)</span>
            <p className="mt-1 text-sm text-gray-700">{invention.anonymized_summary}</p>
          </div>
        )}
      </Card>

      {/* Full Description */}
      {invention.full_description && (
        <Card className="mb-4">
          <h3 className="font-semibold text-sm text-gray-700 mb-2">Full Description</h3>
          <p className="text-sm text-gray-600 whitespace-pre-wrap">{invention.full_description}</p>
        </Card>
      )}

      {/* Claims & Context */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {invention.novelty_claims && invention.novelty_claims.length > 0 && (
          <Card>
            <h3 className="font-semibold text-sm text-gray-700 mb-2">Novelty Claims</h3>
            <ul className="space-y-1">
              {invention.novelty_claims.map((c, i) => (
                <li key={i} className="text-sm text-gray-600 flex gap-2">
                  <span className="text-ndai-500 mt-0.5">•</span>
                  {c}
                </li>
              ))}
            </ul>
          </Card>
        )}
        {invention.potential_applications && invention.potential_applications.length > 0 && (
          <Card>
            <h3 className="font-semibold text-sm text-gray-700 mb-2">Potential Applications</h3>
            <ul className="space-y-1">
              {invention.potential_applications.map((a, i) => (
                <li key={i} className="text-sm text-gray-600 flex gap-2">
                  <span className="text-ndai-500 mt-0.5">•</span>
                  {a}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {/* Value Parameters */}
      <Card className="mb-4">
        <h3 className="font-semibold text-sm text-gray-700 mb-4">Value Parameters</h3>
        <div className="space-y-4">
          {invention.self_assessed_value != null && (
            <ValueBar label="Self-Assessed Value (ω)" value={invention.self_assessed_value} />
          )}
          {invention.outside_option_value != null && (
            <ValueBar label="Outside Option (α₀)" value={invention.outside_option_value} />
          )}
          {invention.max_disclosure_fraction != null && (
            <ValueBar label="Max Disclosure Fraction" value={invention.max_disclosure_fraction} />
          )}
        </div>
      </Card>

      {/* Actions */}
      {invention.status === "active" && (
        <div className="flex gap-3">
          <button
            onClick={handleWithdraw}
            disabled={deleting}
            className="px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 font-medium text-sm transition-colors disabled:opacity-50"
          >
            {deleting ? "Withdrawing..." : "Withdraw"}
          </button>
        </div>
      )}
    </div>
  );
}
