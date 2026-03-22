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

const ALL_CAPABILITIES = ["ace", "lpe", "info_leak", "callback", "crash", "dos"];

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
        const caps = t.supported_capabilities?.length ? t.supported_capabilities : ALL_CAPABILITIES;
        setCapability(caps[0]);
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
      // 1. Fetch enclave attestation
      const { fetchAttestation } = await import("../../api/enclave");
      const { eciesEncrypt } = await import("../../crypto/ecies");

      const nonce = Array.from(crypto.getRandomValues(new Uint8Array(32)))
        .map((b) => b.toString(16).padStart(2, "0")).join("");

      const attestation = await fetchAttestation(nonce);
      if (attestation.error) throw new Error(attestation.error);
      if (!attestation.enclave_public_key) throw new Error("No enclave public key in attestation");

      // 2. Encrypt PoC to enclave's attested public key
      const pubKeyDER = Uint8Array.from(atob(attestation.enclave_public_key), (c) => c.charCodeAt(0));
      const pocBytes = new TextEncoder().encode(pocScript);
      const sealedPocBytes = await eciesEncrypt(pubKeyDER, pocBytes);
      const sealedPocB64 = btoa(String.fromCharCode(...sealedPocBytes));

      // 3. Submit with sealed_poc (encrypted), not poc_script (plaintext)
      const proposal = await createProposal({
        target_id: targetId,
        sealed_poc: sealedPocB64,
        poc_script_type: scriptType,
        claimed_capability: capability,
        reliability_runs: reliabilityRuns,
        asking_price_eth: parseFloat(askingPrice) || 0,
      });
      setProposalId(proposal.id);
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
        <div className="w-6 h-6 border-3 border-zk-border border-t-zk-text animate-spin" />
      </div>
    );
  }

  if (!target) {
    return (
      <div className="border-3 border-zk-border bg-white p-6 text-center">
        <p className="text-red-600 text-sm font-mono">{error || "Target not found"}</p>
      </div>
    );
  }

  const escrowEth = target.escrow_amount_usd / 2000;

  return (
    <div className="max-w-2xl">
      <a href={`#/targets/${targetId}`} className="text-xs text-zk-muted hover:text-zk-text font-mono transition-colors mb-4 inline-block">
        &larr; BACK TO {target.display_name.toUpperCase()}
      </a>

      <h1 className="text-xl font-mono font-extrabold text-zk-text uppercase mb-1">Submit Verification Proposal</h1>
      <p className="text-xs text-zk-muted font-mono mb-6">
        {target.icon_emoji} {target.display_name} v{target.current_version}
      </p>

      {/* Step indicator */}
      <div className="flex items-center gap-0 mb-6">
        {[1, 2, 3].map((s, i) => (
          <React.Fragment key={s}>
            {i > 0 && (
              <div className={`flex-1 h-0.5 ${step >= s ? "bg-zk-accent" : "bg-zk-border"}`} />
            )}
            <div
              className={`w-7 h-7 flex items-center justify-center text-[10px] font-mono font-bold border-2 ${
                step > s
                  ? "bg-emerald-50 text-emerald-700 border-emerald-600"
                  : step === s
                  ? "bg-zk-bg text-zk-accent border-zk-accent"
                  : "bg-white text-zk-dim border-zk-border"
              }`}
            >
              {step > s ? "\u2713" : s}
            </div>
          </React.Fragment>
        ))}
      </div>

      {error && (
        <div className="border-3 border-red-600 bg-red-50 text-red-700 text-xs font-mono p-3 mb-6">
          {error}
        </div>
      )}

      {/* Step 1: PoC Editor */}
      {step === 1 && (
        <div className="space-y-5">
          <div className="border-3 border-zk-border bg-white p-6 space-y-4">
            <h2 className="text-sm font-mono font-bold text-zk-text uppercase flex items-center gap-2">
              <span className="w-5 h-5 flex items-center justify-center border-2 border-zk-accent text-zk-accent text-[10px] font-mono">1</span>
              Proof of Concept
            </h2>

            <PoCEditor
              value={pocScript}
              scriptType={scriptType}
              onValueChange={setPocScript}
              onScriptTypeChange={setScriptType}
            />

            <div>
              <label className="block text-[11px] text-zk-muted font-mono uppercase mb-1">Claimed Capability</label>
              <select
                value={capability}
                onChange={(e) => setCapability(e.target.value)}
                className="w-full px-3 py-2 bg-white border-2 border-zk-border text-sm text-zk-text font-mono outline-none focus:border-zk-accent"
              >
                {(target.supported_capabilities?.length ? target.supported_capabilities : ALL_CAPABILITIES).map((cap) => (
                  <option key={cap} value={cap}>
                    {cap}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[11px] text-zk-muted font-mono uppercase mb-1">Reliability Runs</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={reliabilityRuns}
                  onChange={(e) => setReliabilityRuns(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 bg-white border-2 border-zk-border text-sm text-zk-text font-mono outline-none focus:border-zk-accent"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zk-muted font-mono uppercase mb-1">Asking Price (ETH)</label>
                <input
                  type="text"
                  value={askingPrice}
                  onChange={(e) => setAskingPrice(e.target.value)}
                  placeholder="0.1"
                  className="w-full px-3 py-2 bg-white border-2 border-zk-border text-sm text-zk-text font-mono outline-none focus:border-zk-accent"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleSubmitPoC}
            disabled={submitting || !pocScript.trim()}
            className="w-full py-3 bg-zk-text text-white font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-accent disabled:opacity-50 transition-colors"
          >
            {submitting ? "ENCRYPTING TO ENCLAVE..." : "SEAL & SUBMIT POC"}
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
            className="w-full py-2.5 bg-white border-3 border-zk-border text-zk-text font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-bg transition-colors"
          >
            Back
          </button>
        </div>
      )}

      {/* Step 3: Confirmation */}
      {step === 3 && (
        <div className="space-y-5">
          <div className="border-3 border-zk-border bg-white p-6 space-y-4">
            <h2 className="text-sm font-mono font-bold text-zk-text uppercase flex items-center gap-2">
              <span className="w-5 h-5 flex items-center justify-center border-2 border-emerald-600 text-emerald-700 text-[10px] font-mono">{"\u2713"}</span>
              Ready to Verify
            </h2>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between">
                <span className="text-zk-muted">Target</span>
                <span className="text-zk-text font-bold">{target.display_name} v{target.current_version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Capability</span>
                <span className="text-zk-text">{capability}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Script Type</span>
                <span className="text-zk-text">{scriptType}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Reliability Runs</span>
                <span className="text-zk-text">{reliabilityRuns}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Asking Price</span>
                <span className="text-zk-accent font-bold">{askingPrice} ETH</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zk-muted">Deposit</span>
                <span className="text-emerald-700 font-bold">{badge?.has_badge ? "Waived (badge)" : "Confirmed"}</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleStartVerification}
            disabled={verifying}
            className="w-full py-3 bg-zk-text text-white font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-accent disabled:opacity-50 transition-colors"
          >
            {verifying ? "STARTING VERIFICATION..." : "START VERIFICATION"}
          </button>

          <button
            onClick={() => setStep(badge?.has_badge ? 1 : 2)}
            className="w-full py-2.5 bg-white border-3 border-zk-border text-zk-text font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-bg transition-colors"
          >
            Back
          </button>
        </div>
      )}
    </div>
  );
}
