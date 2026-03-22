import React, { useState, useEffect } from "react";
import { getRFP, submitProposal, type RFPResponse } from "../../api/rfps";
import { LoadingSpinner } from "../../components/LoadingSpinner";

export function ProposalPage({ rfpId }: { rfpId: string }) {
  const [rfp, setRFP] = useState<RFPResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [price, setPrice] = useState(1.0);
  const [days, setDays] = useState(30);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getRFP(rfpId)
      .then(setRFP)
      .catch((e) => setError(e.detail || "Failed to load RFP"))
      .finally(() => setLoading(false));
  }, [rfpId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await submitProposal(rfpId, {
        message: message || undefined,
        proposed_price_eth: price,
        estimated_delivery_days: days,
      });
      window.location.hash = "#/sell";
    } catch (err: any) {
      setError(err.detail || "Failed to submit proposal");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <LoadingSpinner />;
  if (!rfp) return <div className="font-mono text-zk-danger">RFP not found</div>;

  return (
    <div className="max-w-2xl">
      <a href={`#/browse/rfp/${rfpId}`} className="font-mono text-xs text-zk-muted hover:text-zk-accent mb-4 block">
        &larr; BACK TO RFP
      </a>

      <h1 className="font-mono text-headline mb-2">SUBMIT PROPOSAL</h1>
      <p className="text-sm text-zk-muted mb-6">
        Responding to: <span className="font-mono font-bold">{rfp.title}</span>
      </p>

      <div className="zk-card mb-6">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="zk-label">TARGET</div>
            <div className="font-mono text-sm">{rfp.target_software}</div>
          </div>
          <div>
            <div className="zk-label">CAPABILITY</div>
            <div className="font-mono text-sm">{rfp.desired_capability}</div>
          </div>
          <div>
            <div className="zk-label">BUDGET</div>
            <div className="font-mono text-sm">{rfp.budget_min_eth}-{rfp.budget_max_eth} ETH</div>
          </div>
        </div>
      </div>

      {error && (
        <div className="border-2 border-zk-danger p-3 mb-6 font-mono text-sm text-zk-danger">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="zk-label">YOUR PROPOSAL</label>
          <textarea
            className="zk-input resize-y min-h-[120px]"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Describe your capability, methodology, and why you can deliver..."
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="zk-label">PROPOSED PRICE (ETH) *</label>
            <input className="zk-input" type="number" required min={0.01} step={0.01}
              value={price} onChange={(e) => setPrice(parseFloat(e.target.value))} />
          </div>
          <div>
            <label className="zk-label">EST. DELIVERY (DAYS) *</label>
            <input className="zk-input" type="number" required min={1}
              value={days} onChange={(e) => setDays(parseInt(e.target.value))} />
          </div>
        </div>
        <button type="submit" disabled={submitting} className="zk-btn-accent disabled:opacity-50">
          {submitting ? "SUBMITTING..." : "SUBMIT PROPOSAL"}
        </button>
      </form>
    </div>
  );
}
