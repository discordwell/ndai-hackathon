import React, { useState, useEffect } from "react";
import { getTarget } from "../../api/targets";
import { createProposal, confirmDeposit, triggerVerification, getBadgeStatus } from "../../api/proposals";
import type { KnownTargetDetail, BadgeStatus } from "../../api/types";
import { PoCEditor } from "../../components/proposals/PoCEditor";
import { EscrowDeposit } from "../../components/proposals/EscrowDeposit";

interface Props {
  targetId: string;
}

type Step = 1 | 2 | 3;
type ScriptType = "bash" | "python3" | "html" | "powershell";

export function ProposalPage({ targetId }: Props) {
  const [target, setTarget] = useState<KnownTargetDetail | null>(null);
  const [badge, setBadge] = useState<BadgeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [step, setStep] = useState<Step>(1);

  // Form state
  const [pocScript, setPocScript] = useState("");
  const [scriptType, setScriptType] = useState<ScriptType>("bash");
  const [capability, setCapability] = useState("");
  const [reliabilityRuns, setReliabilityRuns] = useState(3);
  const [askingPrice, setAskingPrice] = useState("0.1");

  // Proposal state
  const [proposalId, setProposalId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    Promise.all([
      getTarget(targetId),
      getBadgeStatus().catch(() => ({ has_badge: false, badge_tier: null, eth_address: null, purchased_at: null })),
    ])
      .then(([t, b]) => {
        setTarget(t);
        setBadge(b);
        if (t.supported_capabilities && t.supported_capabilities.length > 0) {
          setCapability(t.supported_capabilities[0]);
        }
      })
      .catch((e) => setError(e.detail || "Failed to load target"))
      .finally(() => setLoading(false));
  }, [targetId]);

  async function handleSubmitPoC() {
    if (!pocScript.trim()) {
      setError("PoC script is required");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const proposal = await createProposal({
        target_id: targetId,
        poc_script: pocScript,
        script_type: scriptType,
        claimed_capability: capability,
        reliability_runs: reliabilityRuns,
        asking_price_eth: parseFloat(askingPrice) || 0,
      });
      setProposalId(proposal.id);
      // Skip escrow step if badge holder
      if (badge?.has_badge) {
        setStep(3);
      } else {
        setStep(2);
      }
    } catch (err: any) {
      setError(err.detail || "Failed to submit proposal");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeposited(txHash: string) {
    if (!proposalId) return;
    setError("");
    try {
      await confirmDeposit(proposalId, txHash);
      setStep(3);
    } catch (err: any) {
      setError(err.detail || "Failed to confirm deposit");
    }
  }

  async function handleStartVerification() {
    if (!proposalId) return;
    setVerifying(true);
    setError("");
    try {
      await triggerVerification(proposalId);
      window.location.hash = `#/proposals/${proposalId}`;
    } catch (err: any) {
      setError(err.detail || "Failed to start verification");
    } finally {
      setVerifying(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  if (!target) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-danger-400 text-sm">{error || "Target not found"}</p>
      </div>
    );
  }

  const escrowEth = target.escrow_amount_usd / 2000; // rough USD/ETH conversion

  return (
    <div className="animate-fade-in max-w-2xl">
      <a href={`#/targets/${targetId}`} className="text-xs text-gray-500 hover:text-gray-300 transition-colors mb-4 inline-block">
        &larr; Back to {target.display_name}
      </a>

      <h1 className="text-xl font-bold text-white mb-1">Submit Verification Proposal</h1>
      <p className="text-xs text-gray-500 mb-6">
        {target.icon_emoji} {target.display_name} v{target.current_version}
      </p>

      {/* Step indicator */}
      <div className="flex items-center gap-0 mb-6">
        {[1, 2, 3].map((s, i) => (
          <React.Fragment key={s}>
            {i > 0 && (
              <div className={`flex-1 h-px ${step >= s ? "bg-accent-400/40" : "bg-surface-700"}`} />
            )}
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold border ${
                step > s
                  ? "bg-success-500/20 text-success-400 border-success-500/30"
                  : step === s
                  ? "bg-accent-400/20 text-accent-400 border-accent-400/30"
                  : "bg-surface-800 text-gray-600 border-surface-700"
              }`}
            >
              {step > s ? "\u2713" : s}
            </div>
          </React.Fragment>
        ))}
      </div>

      {error && (
        <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Step 1: PoC Editor */}
      {step === 1 && (
        <div className="space-y-5">
          <div className="glass-card p-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
              <span className="w-5 h-5 rounded bg-accent-400/10 text-accent-400 text-[10px] font-mono flex items-center justify-center">1</span>
              Proof of Concept
            </h2>

            <PoCEditor
              value={pocScript}
              scriptType={scriptType}
              onValueChange={setPocScript}
              onScriptTypeChange={setScriptType}
            />

            <div>
              <label className="block text-[11px] text-gray-500 mb-1">Claimed Capability</label>
              <select
                value={capability}
                onChange={(e) => setCapability(e.target.value)}
                className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
              >
                {(target.supported_capabilities || []).map((cap) => (
                  <option key={cap} value={cap}>
                    {cap}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] text-gray-500 mb-1">Reliability Runs</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={reliabilityRuns}
                  onChange={(e) => setReliabilityRuns(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
                />
              </div>
              <div>
                <label className="block text-[11px] text-gray-500 mb-1">Asking Price (ETH)</label>
                <input
                  type="text"
                  value={askingPrice}
                  onChange={(e) => setAskingPrice(e.target.value)}
                  placeholder="0.1"
                  className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-white outline-none focus:border-accent-500/50"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleSubmitPoC}
            disabled={submitting || !pocScript.trim()}
            className="w-full py-3 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 disabled:opacity-50 transition-colors text-sm"
          >
            {submitting ? "Submitting..." : "Continue to Deposit"}
          </button>
        </div>
      )}

      {/* Step 2: Escrow */}
      {step === 2 && (
        <div className="space-y-5">
          <EscrowDeposit
            requiredAmountEth={escrowEth}
            hasBadge={badge?.has_badge || false}
            onDeposited={handleDeposited}
          />

          <button
            onClick={() => setStep(1)}
            className="w-full py-2.5 bg-surface-800 border border-surface-700 text-white font-medium rounded-lg hover:bg-surface-700 transition-colors text-sm"
          >
            Back
          </button>
        </div>
      )}

      {/* Step 3: Confirmation */}
      {step === 3 && (
        <div className="space-y-5">
          <div className="glass-card p-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
              <span className="w-5 h-5 rounded bg-success-500/10 text-success-400 text-[10px] font-mono flex items-center justify-center">{"\u2713"}</span>
              Ready to Verify
            </h2>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-500">Target</span>
                <span className="text-gray-300">{target.display_name} v{target.current_version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Capability</span>
                <span className="text-gray-300 font-mono">{capability}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Script Type</span>
                <span className="text-gray-300 font-mono">{scriptType}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Reliability Runs</span>
                <span className="text-gray-300 font-mono">{reliabilityRuns}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Asking Price</span>
                <span className="text-accent-400 font-mono">{askingPrice} ETH</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Deposit</span>
                <span className="text-success-400">{badge?.has_badge ? "Waived (badge)" : "Confirmed"}</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleStartVerification}
            disabled={verifying}
            className="w-full py-3 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 disabled:opacity-50 transition-colors text-sm"
          >
            {verifying ? "Starting Verification..." : "Start Verification"}
          </button>

          <button
            onClick={() => setStep(badge?.has_badge ? 1 : 2)}
            className="w-full py-2.5 bg-surface-800 border border-surface-700 text-white font-medium rounded-lg hover:bg-surface-700 transition-colors text-sm"
          >
            Back
          </button>
        </div>
      )}
    </div>
  );
}
