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
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  if (!proposal) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-danger-400 text-sm">{error || "Proposal not found"}</p>
      </div>
    );
  }

  const isVerifying = proposal.status === "verifying" || proposal.status === "building";
  const isPassed = proposal.verification_result?.passed === true;
  const isFailed = proposal.verification_result?.passed === false;

  return (
    <div className="animate-fade-in max-w-3xl">
      <a href="#/proposals" className="text-xs text-gray-500 hover:text-gray-300 transition-colors mb-4 inline-block">
        &larr; Back to Proposals
      </a>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Proposal Status</h1>
          <p className="text-xs font-mono text-gray-500 mt-1">{proposalId}</p>
        </div>
        <span
          className={`text-xs px-3 py-1 rounded border font-medium ${
            proposal.status === "passed"
              ? "bg-success-500/20 text-success-400 border-success-500/30"
              : proposal.status === "failed"
              ? "bg-danger-500/20 text-danger-400 border-danger-500/30"
              : proposal.status === "verifying" || proposal.status === "building"
              ? "bg-accent-400/20 text-accent-400 border-accent-400/30"
              : "bg-surface-700 text-gray-400 border-surface-600"
          }`}
        >
          {proposal.status}
        </span>
      </div>

      {error && (
        <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Proposal Info */}
        <div className="space-y-6">
          <div className="glass-card p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Proposal Info</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-500">Target</span>
                <span className="text-gray-300">{proposal.target_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Capability</span>
                <span className="text-gray-300 font-mono">{proposal.claimed_capability}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Script Type</span>
                <span className="text-gray-300 font-mono">{proposal.script_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Reliability Runs</span>
                <span className="text-gray-300 font-mono">{proposal.reliability_runs}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Asking Price</span>
                <span className="text-accent-400 font-mono">{proposal.asking_price_eth} ETH</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Deposit</span>
                <span className={proposal.deposit_confirmed ? "text-success-400" : "text-gray-500"}>
                  {proposal.deposit_confirmed ? "Confirmed" : "Pending"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Verification */}
        <div className="lg:col-span-2 space-y-6">
          {isVerifying && (
            <VerificationProgress
              proposalId={proposalId}
              onComplete={() => {
                // Reload proposal to get updated status
                getProposal(proposalId).then(setProposal).catch(() => {});
              }}
            />
          )}

          {/* Already completed result */}
          {proposal.verification_result && !isVerifying && (
            <div
              className={`glass-card p-5 border ${
                isPassed
                  ? "border-success-500/30"
                  : "border-danger-500/30"
              }`}
            >
              <h3 className="text-sm font-semibold mb-3">
                {isPassed ? (
                  <span className="text-success-400">Verification Passed</span>
                ) : (
                  <span className="text-danger-400">Verification Failed</span>
                )}
              </h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">Claimed</span>
                  <span className="text-gray-300 font-mono">{proposal.verification_result.claimed_capability}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Verified</span>
                  <span className="text-gray-300 font-mono">{proposal.verification_result.verified_capability}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Reliability</span>
                  <span className="text-accent-400 font-mono">
                    {(proposal.verification_result.reliability_score * 100).toFixed(0)}%
                  </span>
                </div>
                {proposal.verification_result.error && (
                  <p className="text-danger-400 mt-2">{proposal.verification_result.error}</p>
                )}
              </div>
            </div>
          )}

          {/* Link to listing on pass */}
          {isPassed && proposal.listing_id && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-success-400 mb-2">Listing Created</h3>
              <p className="text-xs text-gray-400 mb-3">
                Your verified vulnerability has been listed on the marketplace.
              </p>
              <a
                href={`#/marketplace/${proposal.listing_id}`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-accent-400 text-surface-950 font-medium rounded-lg hover:bg-accent-300 transition-colors text-xs"
              >
                View Listing &rarr;
              </a>
            </div>
          )}

          {/* Error details on fail */}
          {isFailed && proposal.verification_result?.error && (
            <div className="glass-card p-5 border border-danger-500/30">
              <h3 className="text-sm font-semibold text-danger-400 mb-2">Error Details</h3>
              <pre className="text-xs text-gray-400 font-mono whitespace-pre-wrap bg-surface-900 rounded-lg p-3 border border-surface-700">
                {proposal.verification_result.error}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
