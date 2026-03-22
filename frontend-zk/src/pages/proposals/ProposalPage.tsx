import React, { useState, useEffect } from "react";
import { getTarget } from "../../api/targets";
import { createProposal, confirmDeposit, triggerVerification, getBadgeStatus } from "../../api/proposals";
import type { KnownTargetDetail, BadgeStatus } from "../../api/types";
import { PoCEditor } from "../../components/proposals/PoCEditor";
import { EscrowDeposit } from "../../components/proposals/EscrowDeposit";

interface Props {
  targetId: string;
}

type Step = 1 | 2 | 3 | 4;
type ScriptType = "bash" | "python3" | "html" | "powershell";
type SealStatus = "idle" | "attesting" | "encrypting" | "submitting" | "done" | "error";

const ALL_CAPABILITIES = ["ace", "lpe", "info_leak", "callback", "crash", "dos"];

const STEP_LABELS = ["Write PoC", "Seal to Enclave", "Escrow", "Verify"];

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

  // Seal state
  const [sealStatus, setSealStatus] = useState<SealStatus>("idle");
  const [attestationPcr0, setAttestationPcr0] = useState("");
  const [attestationMode, setAttestationMode] = useState("");
  const [sealedSize, setSealedSize] = useState(0);

  // Proposal state
  const [proposalId, setProposalId] = useState<string | null>(null);
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

  // Step 1 → Step 2: Move to sealing step
  function handleContinueToSeal() {
    if (!pocScript.trim()) {
      setError("PoC script is required");
      return;
    }
    setError("");
    setStep(2);
  }

  // Step 2: Fetch attestation, encrypt, submit
  async function handleSealAndSubmit() {
    setSealStatus("attesting");
    setError("");
    try {
      // 1. Fetch enclave attestation
      const { fetchAttestation } = await import("../../api/enclave");
      const nonce = Array.from(crypto.getRandomValues(new Uint8Array(32)))
        .map((b) => b.toString(16).padStart(2, "0")).join("");

      const attestation = await fetchAttestation(nonce);
      if (attestation.error) throw new Error(attestation.error);
      if (!attestation.enclave_public_key) throw new Error("No enclave public key in attestation");

      setAttestationPcr0(attestation.pcr0?.slice(0, 16) || "");
      setAttestationMode(attestation.mode);

      // 2. Encrypt PoC to enclave's attested public key
      setSealStatus("encrypting");
      const { eciesEncrypt } = await import("../../crypto/ecies");
      const pubKeyDER = Uint8Array.from(atob(attestation.enclave_public_key), (c) => c.charCodeAt(0));
      const pocBytes = new TextEncoder().encode(pocScript);
      const sealedPocBytes = await eciesEncrypt(pubKeyDER, pocBytes);
      const sealedPocB64 = btoa(String.fromCharCode(...sealedPocBytes));
      setSealedSize(sealedPocBytes.length);

      // 3. Submit sealed proposal
      setSealStatus("submitting");
      const proposal = await createProposal({
        target_id: targetId,
        sealed_poc: sealedPocB64,
        poc_script_type: scriptType,
        claimed_capability: capability,
        reliability_runs: reliabilityRuns,
        asking_price_eth: parseFloat(askingPrice) || 0,
      });

      setProposalId(proposal.id);
      setSealStatus("done");

      // Auto-advance after brief pause
      setTimeout(() => {
        if (badge?.has_badge) {
          setStep(4);
        } else {
          setStep(3);
        }
      }, 1500);
    } catch (err: any) {
      setSealStatus("error");
      setError(err.detail || err.message || "Sealing failed");
    }
  }

  async function handleDeposited(txHash: string) {
    if (!proposalId) return;
    setError("");
    try {
      await confirmDeposit(proposalId, txHash);
      setStep(4);
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

      {/* Step indicator — 4 steps */}
      <div className="flex items-center gap-0 mb-6">
        {STEP_LABELS.map((label, i) => {
          const s = i + 1;
          return (
            <React.Fragment key={s}>
              {i > 0 && (
                <div className={`flex-1 h-0.5 ${step >= s ? "bg-zk-accent" : "bg-zk-border"}`} />
              )}
              <div className="flex flex-col items-center gap-1">
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
                <span className={`text-[9px] font-mono uppercase ${step === s ? "text-zk-accent font-bold" : "text-zk-dim"}`}>
                  {label}
                </span>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {error && (
        <div className="border-3 border-red-600 bg-red-50 text-red-700 text-xs font-mono p-3 mb-6">
          {error}
        </div>
      )}

      {/* Step 1: Write PoC */}
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
            onClick={handleContinueToSeal}
            disabled={!pocScript.trim()}
            className="w-full py-3 bg-zk-text text-white font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-accent disabled:opacity-50 transition-colors"
          >
            CONTINUE TO SEAL
          </button>
        </div>
      )}

      {/* Step 2: Seal to Enclave */}
      {step === 2 && (
        <div className="space-y-5">
          <div className="border-3 border-zk-border bg-white p-6 space-y-4">
            <h2 className="text-sm font-mono font-bold text-zk-text uppercase flex items-center gap-2">
              <span className="w-5 h-5 flex items-center justify-center border-2 border-zk-accent text-zk-accent text-[10px] font-mono">2</span>
              Seal to Enclave
            </h2>

            <p className="text-xs text-zk-muted font-mono leading-relaxed">
              Your PoC will be encrypted to the verification enclave's attested public key.
              The platform operator cannot read your exploit — only the hardware-isolated
              enclave can decrypt it.
            </p>

            {/* Seal progress */}
            <div className="bg-zk-bg border-2 border-zk-border p-4 space-y-3">
              <SealStep
                label="Fetch enclave attestation"
                detail={attestationPcr0 ? `PCR0: ${attestationPcr0}... (${attestationMode})` : undefined}
                status={sealStatus === "attesting" ? "active" : sealStatus === "idle" ? "pending" : "done"}
              />
              <SealStep
                label="Encrypt PoC (ECIES P-384 + AES-256-GCM)"
                detail={sealedSize ? `${sealedSize} bytes ciphertext` : undefined}
                status={sealStatus === "encrypting" ? "active" : ["idle", "attesting"].includes(sealStatus) ? "pending" : "done"}
              />
              <SealStep
                label="Submit sealed proposal"
                status={sealStatus === "submitting" ? "active" : ["idle", "attesting", "encrypting"].includes(sealStatus) ? "pending" : "done"}
              />
            </div>

            {sealStatus === "done" && (
              <div className="border-2 border-emerald-600 bg-emerald-50 p-3">
                <p className="text-xs font-mono text-emerald-700 font-bold uppercase">
                  PoC sealed. Only the enclave can decrypt it.
                </p>
              </div>
            )}

            {sealStatus === "error" && (
              <div className="border-2 border-red-600 bg-red-50 p-3">
                <p className="text-xs font-mono text-red-700">
                  Sealing failed. Your PoC was NOT sent. Try again.
                </p>
              </div>
            )}

            {/* Trust explainer */}
            {sealStatus === "idle" && (
              <div className="text-[11px] text-zk-dim font-mono space-y-1">
                <p>1. The attestation is signed by AWS Nitro hardware, not the host</p>
                <p>2. PCR0 proves the exact code running in the enclave</p>
                <p>3. The public key is bound to the attestation — MITM is detectable</p>
                <p>4. Your PoC is encrypted client-side — plaintext never leaves your browser</p>
              </div>
            )}
          </div>

          {sealStatus === "idle" || sealStatus === "error" ? (
            <>
              <button
                onClick={handleSealAndSubmit}
                className="w-full py-3 bg-zk-text text-white font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-accent transition-colors"
              >
                SEAL & SUBMIT
              </button>
              <button
                onClick={() => { setStep(1); setSealStatus("idle"); setError(""); }}
                className="w-full py-2.5 bg-white border-3 border-zk-border text-zk-text font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-bg transition-colors"
              >
                Back
              </button>
            </>
          ) : sealStatus !== "done" ? (
            <div className="text-center text-xs font-mono text-zk-muted animate-pulse">
              Sealing in progress...
            </div>
          ) : null}
        </div>
      )}

      {/* Step 3: Escrow */}
      {step === 3 && (
        <div className="space-y-5">
          <EscrowDeposit
            requiredAmountEth={escrowEth}
            hasBadge={badge?.has_badge || false}
            onDeposited={handleDeposited}
          />

          <button
            onClick={() => setStep(2)}
            className="w-full py-2.5 bg-white border-3 border-zk-border text-zk-text font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-bg transition-colors"
          >
            Back
          </button>
        </div>
      )}

      {/* Step 4: Confirm & Verify */}
      {step === 4 && (
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
              <div className="flex justify-between">
                <span className="text-zk-muted">PoC Sealed</span>
                <span className="text-emerald-700 font-bold">{sealedSize} bytes ciphertext</span>
              </div>
              {attestationPcr0 && (
                <div className="flex justify-between">
                  <span className="text-zk-muted">Enclave PCR0</span>
                  <span className="text-zk-text">{attestationPcr0}...</span>
                </div>
              )}
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
            onClick={() => setStep(badge?.has_badge ? 2 : 3)}
            className="w-full py-2.5 bg-white border-3 border-zk-border text-zk-text font-mono font-bold text-sm uppercase tracking-wider hover:bg-zk-bg transition-colors"
          >
            Back
          </button>
        </div>
      )}
    </div>
  );
}

// Sub-component for seal progress steps
function SealStep({ label, detail, status }: { label: string; detail?: string; status: "pending" | "active" | "done" }) {
  return (
    <div className="flex items-start gap-3">
      <div className={`w-5 h-5 flex items-center justify-center shrink-0 mt-0.5 ${
        status === "done"
          ? "text-emerald-600"
          : status === "active"
          ? "text-zk-accent animate-pulse"
          : "text-zk-dim"
      }`}>
        {status === "done" ? (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        ) : status === "active" ? (
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        ) : (
          <div className="w-2 h-2 rounded-full bg-zk-border" />
        )}
      </div>
      <div>
        <span className={`text-xs font-mono ${status === "active" ? "text-zk-accent font-bold" : status === "done" ? "text-zk-text" : "text-zk-dim"}`}>
          {label}
        </span>
        {detail && (
          <div className="text-[10px] font-mono text-zk-muted mt-0.5">{detail}</div>
        )}
      </div>
    </div>
  );
}
