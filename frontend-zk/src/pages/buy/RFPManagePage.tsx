import React, { useState, useEffect } from "react";
import { getRFP, listProposals, acceptProposal, cancelRFP, type RFPResponse, type ProposalResponse } from "../../api/rfps";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { StatusBadge } from "../../components/StatusBadge";
import { EmptyState } from "../../components/EmptyState";

export function RFPManagePage({ id }: { id: string }) {
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

  async function handleAccept(proposalId: string) {
    try {
      await acceptProposal(proposalId);
      window.location.reload();
    } catch (err: any) {
      setError(err.detail || "Failed to accept proposal");
    }
  }

  async function handleCancel() {
    try {
      await cancelRFP(id);
      window.location.hash = "#/buy";
    } catch (err: any) {
      setError(err.detail || "Failed to cancel");
    }
  }

  if (loading) return <LoadingSpinner />;
  if (!rfp) return <div className="font-mono text-zk-danger">RFP not found</div>;

  return (
    <div className="max-w-3xl">
      <a href="#/buy" className="font-mono text-xs text-zk-muted hover:text-zk-accent mb-4 block">
        &larr; BACK TO MY RFPS
      </a>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="font-mono text-headline leading-tight">{rfp.title}</h1>
          <p className="font-mono text-sm text-zk-muted mt-1">
            {rfp.target_software} {rfp.target_version_range} / {rfp.desired_capability}
          </p>
        </div>
        <StatusBadge status={rfp.status} />
      </div>

      {error && (
        <div className="border-2 border-zk-danger p-3 mb-6 font-mono text-sm text-zk-danger">{error}</div>
      )}

      <div className="zk-card mb-6">
        <div className="grid grid-cols-3 gap-6">
          <div>
            <div className="zk-label">BUDGET</div>
            <div className="font-mono text-sm font-bold">{rfp.budget_min_eth}-{rfp.budget_max_eth} ETH</div>
          </div>
          <div>
            <div className="zk-label">DEADLINE</div>
            <div className="font-mono text-sm font-bold">{rfp.deadline.split("T")[0]}</div>
          </div>
          <div>
            <div className="zk-label">PATCHES</div>
            <div className="font-mono text-sm font-bold">{rfp.has_patches ? "YES" : "NO"}</div>
          </div>
        </div>
      </div>

      <div className="zk-section-title">PROPOSALS ({proposals.length})</div>

      {proposals.length === 0 ? (
        <EmptyState message="No proposals received yet" />
      ) : (
        <div className="space-y-3">
          {proposals.map((p) => (
            <div key={p.id} className="zk-card">
              <div className="flex items-center gap-4 mb-3">
                <StatusBadge status={p.status} />
                <span className="font-mono text-lg font-bold">{p.proposed_price_eth} ETH</span>
                <span className="font-mono text-xs text-zk-muted">{p.estimated_delivery_days} days delivery</span>
                <span className="flex-1" />
                <span className="font-mono text-xs text-zk-dim">{p.created_at.split("T")[0]}</span>
              </div>
              {p.message && <p className="text-sm mb-3">{p.message}</p>}
              {p.status === "pending" && rfp.status === "active" && (
                <button onClick={() => handleAccept(p.id)} className="zk-btn-accent">
                  ACCEPT PROPOSAL
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {rfp.status === "active" && (
        <div className="mt-8 pt-6 border-t-2 border-zk-border">
          <button onClick={handleCancel} className="font-mono text-xs text-zk-danger hover:underline">
            CANCEL THIS RFP
          </button>
        </div>
      )}
    </div>
  );
}
