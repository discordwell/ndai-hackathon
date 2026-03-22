import React, { useState, useEffect } from "react";
import { getProposal } from "../../api/proposals";
import type { ProposalDetail } from "../../api/types";
import { VerificationProgress } from "../../components/proposals/VerificationProgress";

interface Props {
  proposalId: string;
}

export function ProposalStatusPage({ proposalId }: Props) {
  const [proposal, setProposal] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getProposal(proposalId)
      .then(setProposal)
      .catch((e) => setError(e.detail || "Failed to load proposal"))
      .finally(() => setLoading(false));
  }, [proposalId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-3 border-zk-border border-t-zk-text animate-spin" />
      </div>
    );
  }

  if (!proposal) {
    return (
      <div className="border-3 border-zk-border bg-white p-6 text-center">
        <p className="text-red-600 text-sm font-mono">{error || "Proposal not found"}</p>
      </div>
    );
  }

  const isVerifying = proposal.status === "verifying" || proposal.status === "building";
  const isPassed = proposal.verification_result?.passed === true;
  const isFailed = proposal.verification_result?.passed === false;

  return (
    <div className="max-w-3xl">
      <a href="#/proposals" className="text-xs text-zk-muted hover:text-zk-text font-mono transition-colors mb-4 inline-block">
        &larr; BACK TO PROPOSALS
      </a>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-mono font-extrabold text-zk-text uppercase">Proposal Status</h1>
          <p className="text-xs font-mono text-zk-muted mt-1">{proposalId}</p>
        </div>
        <span
          className={`text-xs px-3 py-1 border-2 font-mono font-bold uppercase ${
            proposal.status === "passed"
              ? "text-emerald-700 border-emerald-600"
              : proposal.status === "failed"
              ? "text-red-700 border-red-600"
              : proposal.status === "verifying" || proposal.status === "building"
              ? "text-zk-accent border-zk-accent"
              : "text-zk-muted border-zk-border"
          }`}
        >
          {proposal.status}
        </span>
      </div>

      {error && (
        <div className="border-3 border-red-600 bg-red-50 text-red-700 text-xs font-mono p-3 mb-6">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Proposal Info */}
        <div className="space-y-4">
          <div className="border-3 border-zk-border bg-white p-5">
            <h3 className="text-xs font-mono font-bold text-zk-dim uppercase tracking-wider mb-3">Proposal Info</h3>
            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-zk-muted">Target</span>
                <span className="text-zk-text font-bold">{proposal.target_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Capability</span>
                <span className="text-zk-text">{proposal.claimed_capability}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Script Type</span>
                <span className="text-zk-text">{proposal.script_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Reliability Runs</span>
                <span className="text-zk-text">{proposal.reliability_runs}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Asking Price</span>
                <span className="text-zk-accent font-bold">{proposal.asking_price_eth} ETH</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Deposit</span>
                <span className={proposal.deposit_confirmed ? "text-emerald-700 font-bold" : "text-zk-muted"}>
                  {proposal.deposit_confirmed ? "Confirmed" : "Pending"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Verification */}
        <div className="lg:col-span-2 space-y-4">
          {isVerifying && (
            <VerificationProgress
              proposalId={proposalId}
              onComplete={() => {
                getProposal(proposalId).then(setProposal).catch(() => {});
              }}
            />
          )}

          {/* Already completed result */}
          {proposal.verification_result && !isVerifying && (
            <div
              className={`border-3 bg-white p-5 ${
                isPassed
                  ? "border-emerald-600"
                  : "border-red-600"
              }`}
            >
              <h3 className="text-sm font-mono font-bold uppercase mb-3">
                {isPassed ? (
                  <span className="text-emerald-700">Verification Passed</span>
                ) : (
                  <span className="text-red-700">Verification Failed</span>
                )}
              </h3>
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-zk-muted">Claimed</span>
                  <span className="text-zk-text">{proposal.verification_result.claimed_capability}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zk-muted">Verified</span>
                  <span className="text-zk-text">{proposal.verification_result.verified_capability}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zk-muted">Reliability</span>
                  <span className="text-zk-accent font-bold">
                    {(proposal.verification_result.reliability_score * 100).toFixed(0)}%
                  </span>
                </div>
                {proposal.verification_result.error && (
                  <p className="text-red-600 mt-2">{proposal.verification_result.error}</p>
                )}
              </div>
            </div>
          )}

          {/* Link to listing on pass */}
          {isPassed && proposal.listing_id && (
            <div className="border-3 border-emerald-600 bg-white p-5">
              <h3 className="text-sm font-mono font-bold text-emerald-700 uppercase mb-2">Listing Created</h3>
              <p className="text-xs text-zk-muted font-mono mb-3">
                Your verified vulnerability has been listed on the marketplace.
              </p>
              <a
                href={`#/browse/vuln/${proposal.listing_id}`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-zk-text text-white font-mono font-bold text-xs uppercase tracking-wider hover:bg-zk-accent transition-colors"
              >
                View Listing &rarr;
              </a>
            </div>
          )}

          {/* Error details on fail */}
          {isFailed && proposal.verification_result?.error && (
            <div className="border-3 border-red-600 bg-white p-5">
              <h3 className="text-sm font-mono font-bold text-red-700 uppercase mb-2">Error Details</h3>
              <pre className="text-xs text-zk-text font-mono whitespace-pre-wrap bg-zk-bg border-2 border-zk-border p-3">
                {proposal.verification_result.error}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
