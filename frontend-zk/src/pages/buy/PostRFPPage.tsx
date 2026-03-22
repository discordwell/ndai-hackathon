import React, { useState } from "react";
import { createRFP, uploadPatches } from "../../api/rfps";

export function PostRFPPage() {
  const [form, setForm] = useState({
    title: "",
    target_software: "",
    target_version_range: "",
    desired_capability: "RCE",
    threat_model: "",
    target_env_os: "",
    target_env_version: "",
    target_env_config: "",
    acceptance_criteria: "",
    budget_min_eth: 0.5,
    budget_max_eth: 5.0,
    deadline: "",
    exclusivity_preference: "either",
  });
  const [patchFile, setPatchFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(field: string, value: string | number) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const target_environment: Record<string, unknown> = {};
      if (form.target_env_os) target_environment.os = form.target_env_os;
      if (form.target_env_version) target_environment.version = form.target_env_version;
      if (form.target_env_config) target_environment.config = form.target_env_config;

      const rfp = await createRFP({
        title: form.title,
        target_software: form.target_software,
        target_version_range: form.target_version_range,
        desired_capability: form.desired_capability,
        threat_model: form.threat_model || undefined,
        target_environment: Object.keys(target_environment).length > 0 ? target_environment : undefined,
        acceptance_criteria: form.acceptance_criteria || undefined,
        budget_min_eth: form.budget_min_eth,
        budget_max_eth: form.budget_max_eth,
        deadline: form.deadline,
        exclusivity_preference: form.exclusivity_preference,
      });

      if (patchFile) {
        await uploadPatches(rfp.id, patchFile);
      }

      window.location.hash = "#/buy";
    } catch (err: any) {
      setError(err.detail || "Submission failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="font-mono text-headline mb-2">POST RFP</h1>
      <p className="text-sm text-zk-muted mb-8">
        Request a specific vulnerability from researchers. Include threat model,
        acceptance criteria, and optionally attach custom patches for overlap detection.
      </p>

      {error && (
        <div className="border-2 border-zk-danger p-3 mb-6 font-mono text-sm text-zk-danger">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="zk-section-title">REQUEST</div>
        <div>
          <label className="zk-label">TITLE *</label>
          <input className="zk-input" required value={form.title}
            onChange={(e) => set("title", e.target.value)}
            placeholder="e.g., Pre-auth RCE in OpenSSH 9.x" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="zk-label">TARGET SOFTWARE *</label>
            <input className="zk-input" required value={form.target_software}
              onChange={(e) => set("target_software", e.target.value)}
              placeholder="e.g., OpenSSH" />
          </div>
          <div>
            <label className="zk-label">VERSION RANGE *</label>
            <input className="zk-input" required value={form.target_version_range}
              onChange={(e) => set("target_version_range", e.target.value)}
              placeholder="e.g., 8.0 - 9.6" />
          </div>
        </div>
        <div>
          <label className="zk-label">DESIRED CAPABILITY *</label>
          <select className="zk-select" value={form.desired_capability}
            onChange={(e) => set("desired_capability", e.target.value)}>
            <option value="RCE">RCE — Remote Code Execution</option>
            <option value="LPE">LPE — Local Privilege Escalation</option>
            <option value="InfoLeak">InfoLeak — Information Disclosure</option>
            <option value="DoS">DoS — Denial of Service</option>
          </select>
        </div>

        <div className="zk-section-title">THREAT MODEL</div>
        <div>
          <label className="zk-label">DESCRIPTION</label>
          <textarea className="zk-input resize-y min-h-[120px]" value={form.threat_model}
            onChange={(e) => set("threat_model", e.target.value)}
            placeholder="Describe the threat scenario, attacker capabilities, and what you need to defend against..." />
        </div>

        <div className="zk-section-title">TARGET ENVIRONMENT</div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="zk-label">OPERATING SYSTEM</label>
            <input className="zk-input" value={form.target_env_os}
              onChange={(e) => set("target_env_os", e.target.value)}
              placeholder="e.g., Ubuntu 22.04" />
          </div>
          <div>
            <label className="zk-label">SOFTWARE VERSION</label>
            <input className="zk-input" value={form.target_env_version}
              onChange={(e) => set("target_env_version", e.target.value)}
              placeholder="e.g., 9.2p1" />
          </div>
        </div>
        <div>
          <label className="zk-label">CONFIGURATION DETAILS</label>
          <textarea className="zk-input resize-y min-h-[80px]" value={form.target_env_config}
            onChange={(e) => set("target_env_config", e.target.value)}
            placeholder="Relevant configuration, hardening measures, network topology..." />
        </div>

        <div className="zk-section-title">ACCEPTANCE CRITERIA</div>
        <div>
          <label className="zk-label">WHAT CONSTITUTES SUCCESS</label>
          <textarea className="zk-input resize-y min-h-[100px]" value={form.acceptance_criteria}
            onChange={(e) => set("acceptance_criteria", e.target.value)}
            placeholder="Define what the exploit must achieve, reliability requirements, constraints..." />
        </div>

        <div className="zk-section-title">CUSTOM PATCHES (OPTIONAL)</div>
        <div>
          <label className="zk-label">OVERLAY PATCH FILE</label>
          <p className="text-xs text-zk-muted mb-2">
            Upload patched binaries for overlap detection. If the exploit survives your patches,
            it's a genuinely new 0day. Encrypted to the TEE enclave.
          </p>
          <input
            type="file"
            onChange={(e) => setPatchFile(e.target.files?.[0] || null)}
            className="font-mono text-sm file:zk-btn-sm file:mr-4 file:cursor-pointer"
          />
          {patchFile && (
            <p className="font-mono text-xs text-zk-success mt-1">
              {patchFile.name} ({(patchFile.size / 1024).toFixed(0)} KB)
            </p>
          )}
        </div>

        <div className="zk-section-title">BUDGET & TERMS</div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="zk-label">MIN BUDGET (ETH) *</label>
            <input className="zk-input" type="number" required min={0.01} step={0.01}
              value={form.budget_min_eth}
              onChange={(e) => set("budget_min_eth", parseFloat(e.target.value))} />
          </div>
          <div>
            <label className="zk-label">MAX BUDGET (ETH) *</label>
            <input className="zk-input" type="number" required min={0.01} step={0.01}
              value={form.budget_max_eth}
              onChange={(e) => set("budget_max_eth", parseFloat(e.target.value))} />
          </div>
          <div>
            <label className="zk-label">EXCLUSIVITY</label>
            <select className="zk-select" value={form.exclusivity_preference}
              onChange={(e) => set("exclusivity_preference", e.target.value)}>
              <option value="either">Either</option>
              <option value="exclusive">Exclusive Only</option>
              <option value="non-exclusive">Non-Exclusive OK</option>
            </select>
          </div>
        </div>
        <div>
          <label className="zk-label">DEADLINE *</label>
          <input className="zk-input" type="date" required value={form.deadline}
            onChange={(e) => set("deadline", e.target.value)} />
        </div>

        <div className="pt-4">
          <button type="submit" disabled={loading} className="zk-btn-accent disabled:opacity-50">
            {loading ? "SUBMITTING..." : "POST RFP"}
          </button>
        </div>
      </form>
    </div>
  );
}
