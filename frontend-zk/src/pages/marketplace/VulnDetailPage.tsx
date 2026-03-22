import React, { useState, useEffect } from "react";
import { getVuln, createVulnAgreement, type VulnResponse } from "../../api/vulns";
import { LoadingSpinner } from "../../components/LoadingSpinner";

export function VulnDetailPage({ id }: { id: string }) {
  const [vuln, setVuln] = useState<VulnResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [budgetCap, setBudgetCap] = useState(1.0);
  const [proposing, setProposing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getVuln(id)
      .then(setVuln)
      .catch((e) => setError(e.detail || "Failed to load"))
      .finally(() => setLoading(false));
  }, [id]);

  async function handlePropose() {
    setProposing(true);
    setError("");
    try {
      const agreement = await createVulnAgreement(id, budgetCap);
      window.location.hash = `#/deals/${agreement.id}`;
    } catch (err: any) {
      setError(err.detail || "Failed to propose deal");
    } finally {
      setProposing(false);
    }
  }

  if (loading) return <LoadingSpinner />;
  if (!vuln) return <div className="font-mono text-zk-danger">Vulnerability not found</div>;

  return (
    <div className="max-w-3xl">
      <a href="#/browse" className="font-mono text-xs text-zk-muted hover:text-zk-accent mb-4 block">
        &larr; BACK TO MARKETPLACE
      </a>

      <div className="flex items-start gap-4 mb-6">
        <span className="zk-tag-danger">VULN</span>
        <div>
          <h1 className="font-mono text-headline leading-tight">{vuln.target_software}</h1>
          <p className="font-mono text-sm text-zk-muted mt-1">v{vuln.target_version}</p>
        </div>
      </div>

      <div className="zk-card mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <div className="zk-label">CLASS</div>
            <div className="font-mono text-sm font-bold">{vuln.vulnerability_class}</div>
          </div>
          <div>
            <div className="zk-label">IMPACT</div>
            <div className="font-mono text-sm font-bold">{vuln.impact_type}</div>
          </div>
          <div>
            <div className="zk-label">CVSS</div>
            <div className="font-mono text-2xl font-bold">{vuln.cvss_self_assessed.toFixed(1)}</div>
          </div>
          <div>
            <div className="zk-label">EXCLUSIVITY</div>
            <div className="font-mono text-sm font-bold uppercase">{vuln.exclusivity}</div>
          </div>
        </div>
      </div>

      {error && (
        <div className="border-2 border-zk-danger p-3 mb-6 font-mono text-sm text-zk-danger">{error}</div>
      )}

      <div className="zk-card">
        <div className="zk-section-title">PROPOSE DEAL</div>
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="zk-label">BUDGET CAP (ETH)</label>
            <input
              type="number"
              className="zk-input"
              min={0.01}
              step={0.01}
              value={budgetCap}
              onChange={(e) => setBudgetCap(parseFloat(e.target.value))}
            />
          </div>
          <button
            onClick={handlePropose}
            disabled={proposing}
            className="zk-btn-accent disabled:opacity-50"
          >
            {proposing ? "..." : "PROPOSE DEAL"}
          </button>
        </div>
      </div>
    </div>
  );
}
