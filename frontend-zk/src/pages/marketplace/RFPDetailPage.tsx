import React, { useState, useEffect } from "react";
import { getRFP, listProposals, type RFPResponse, type ProposalResponse } from "../../api/rfps";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { StatusBadge } from "../../components/StatusBadge";

export function RFPDetailPage({ id }: { id: string }) {
  const [rfp, setRFP] = useState<RFPResponse | null>(null);
  const [proposals, setProposals] = useState<ProposalResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getRFP(id), listProposals(id)])
      .then(([r, p]) => { setRFP(r); setProposals(p); })
      .catch((e) => setError(e.detail || "Failed to load"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (!rfp) return <div className="font-mono text-zk-danger">RFP not found</div>;

  const env = rfp.target_environment || {};

  return (
    <div className="max-w-3xl">
      <a href="#/browse" className="font-mono text-xs text-zk-muted hover:text-zk-accent mb-4 block">
        &larr; BACK TO MARKETPLACE
      </a>

      <div className="flex items-start gap-4 mb-6">
        <span className="zk-tag border-zk-link text-zk-link">RFP</span>
        <div>
          <h1 className="font-mono text-headline leading-tight">{rfp.title}</h1>
          <p className="font-mono text-sm text-zk-muted mt-1">
            {rfp.target_software} {rfp.target_version_range}
          </p>
        </div>
      </div>

      {error && (
        <div className="border-2 border-zk-danger p-3 mb-6 font-mono text-sm text-zk-danger">{error}</div>
      )}

      <div className="zk-card mb-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <div className="zk-label">DESIRED CAP</div>
            <div className="font-mono text-sm font-bold">{rfp.desired_capability}</div>
          </div>
          <div>
            <div className="zk-label">BUDGET</div>
            <div className="font-mono text-sm font-bold">{rfp.budget_min_eth}-{rfp.budget_max_eth} ETH</div>
          </div>
          <div>
            <div className="zk-label">DEADLINE</div>
            <div className="font-mono text-sm font-bold">{rfp.deadline.split("T")[0]}</div>
          </div>
          <div>
            <div className="zk-label">STATUS</div>
            <StatusBadge status={rfp.status} />
          </div>
        </div>
      </div>

      {rfp.threat_model && (
        <div className="zk-card mb-4">
          <div className="zk-section-title">THREAT MODEL</div>
          <p className="text-sm whitespace-pre-wrap">{rfp.threat_model}</p>
        </div>
      )}

      {Object.keys(env).length > 0 && (
        <div className="zk-card mb-4">
          <div className="zk-section-title">TARGET ENVIRONMENT</div>
          <pre className="font-mono text-xs bg-zk-bg p-3 overflow-x-auto">
            {JSON.stringify(env, null, 2)}
          </pre>
        </div>
      )}

      {rfp.acceptance_criteria && (
        <div className="zk-card mb-4">
          <div className="zk-section-title">ACCEPTANCE CRITERIA</div>
          <p className="text-sm whitespace-pre-wrap">{rfp.acceptance_criteria}</p>
        </div>
      )}

      <div className="flex gap-2 mb-6">
        {rfp.has_patches && <span className="zk-tag-success">CUSTOM PATCHES ATTACHED</span>}
        <span className="zk-tag">{rfp.exclusivity_preference}</span>
      </div>

      {rfp.status === "active" && (
        <a href={`#/sell/propose/${rfp.id}`} className="zk-btn-accent no-underline">
          SUBMIT PROPOSAL
        </a>
      )}

      {proposals.length > 0 && (
        <div className="mt-8">
          <div className="zk-section-title">PROPOSALS ({proposals.length})</div>
          <div className="space-y-0">
            {proposals.map((p) => (
              <div key={p.id} className="border-2 border-zk-border border-b-0 last:border-b-2 p-4">
                <div className="flex items-center gap-4">
                  <StatusBadge status={p.status} />
                  <span className="font-mono text-sm font-bold">{p.proposed_price_eth} ETH</span>
                  <span className="font-mono text-xs text-zk-muted">{p.estimated_delivery_days} days</span>
                  <span className="flex-1" />
                  <span className="font-mono text-xs text-zk-dim">{p.created_at.split("T")[0]}</span>
                </div>
                {p.message && <p className="text-sm text-zk-muted mt-2">{p.message}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
