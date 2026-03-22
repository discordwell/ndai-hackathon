import React, { useState } from "react";
import { createVuln } from "../../api/vulns";

export function SubmitVulnPage() {
  const [form, setForm] = useState({
    target_software: "",
    target_version: "",
    vulnerability_class: "",
    impact_type: "RCE",
    affected_component: "",
    anonymized_summary: "",
    cvss_self_assessed: 7.0,
    discovery_date: new Date().toISOString().split("T")[0],
    software_category: "default",
    exclusivity: "exclusive",
    embargo_days: 90,
    max_disclosure_level: 3,
    outside_option_value: 0.3,
    patch_status: "unpatched",
  });
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
      await createVuln(form);
      window.location.hash = "#/sell";
    } catch (err: any) {
      setError(err.detail || "Submission failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="font-mono text-headline mb-2">POST VULNERABILITY</h1>
      <p className="text-sm text-zk-muted mb-8">
        List a zero-day vulnerability for sale on the marketplace.
      </p>

      {error && (
        <div className="border-2 border-zk-danger p-3 mb-6 font-mono text-sm text-zk-danger">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="zk-section-title">TARGET</div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="zk-label">SOFTWARE *</label>
            <input className="zk-input" required value={form.target_software}
              onChange={(e) => set("target_software", e.target.value)}
              placeholder="e.g., Apache httpd" />
          </div>
          <div>
            <label className="zk-label">VERSION *</label>
            <input className="zk-input" required value={form.target_version}
              onChange={(e) => set("target_version", e.target.value)}
              placeholder="e.g., 2.4.52" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="zk-label">CWE CLASS *</label>
            <input className="zk-input" required value={form.vulnerability_class}
              onChange={(e) => set("vulnerability_class", e.target.value)}
              placeholder="e.g., CWE-787" />
          </div>
          <div>
            <label className="zk-label">IMPACT TYPE *</label>
            <select className="zk-select" value={form.impact_type}
              onChange={(e) => set("impact_type", e.target.value)}>
              <option value="RCE">RCE — Remote Code Execution</option>
              <option value="LPE">LPE — Local Privilege Escalation</option>
              <option value="InfoLeak">InfoLeak — Information Disclosure</option>
              <option value="DoS">DoS — Denial of Service</option>
            </select>
          </div>
        </div>
        <div>
          <label className="zk-label">AFFECTED COMPONENT</label>
          <input className="zk-input" value={form.affected_component}
            onChange={(e) => set("affected_component", e.target.value)}
            placeholder="e.g., mod_proxy" />
        </div>
        <div>
          <label className="zk-label">ANONYMIZED SUMMARY</label>
          <textarea className="zk-input resize-y min-h-[100px]" value={form.anonymized_summary}
            onChange={(e) => set("anonymized_summary", e.target.value)}
            placeholder="Describe the vulnerability without revealing the exploit..." />
        </div>

        <div className="zk-section-title">ASSESSMENT</div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="zk-label">CVSS *</label>
            <input className="zk-input" type="number" required min={0} max={10} step={0.1}
              value={form.cvss_self_assessed}
              onChange={(e) => set("cvss_self_assessed", parseFloat(e.target.value))} />
          </div>
          <div>
            <label className="zk-label">DISCOVERY DATE *</label>
            <input className="zk-input" type="date" required value={form.discovery_date}
              onChange={(e) => set("discovery_date", e.target.value)} />
          </div>
          <div>
            <label className="zk-label">CATEGORY</label>
            <select className="zk-select" value={form.software_category}
              onChange={(e) => set("software_category", e.target.value)}>
              <option value="default">Default</option>
              <option value="browser">Browser</option>
              <option value="os_kernel">OS / Kernel</option>
              <option value="mobile">Mobile</option>
              <option value="embedded">Embedded</option>
              <option value="cloud">Cloud / SaaS</option>
            </select>
          </div>
        </div>

        <div className="zk-section-title">TERMS</div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="zk-label">EXCLUSIVITY</label>
            <select className="zk-select" value={form.exclusivity}
              onChange={(e) => set("exclusivity", e.target.value)}>
              <option value="exclusive">Exclusive</option>
              <option value="non-exclusive">Non-Exclusive</option>
            </select>
          </div>
          <div>
            <label className="zk-label">EMBARGO (DAYS)</label>
            <input className="zk-input" type="number" min={0} max={365}
              value={form.embargo_days}
              onChange={(e) => set("embargo_days", parseInt(e.target.value))} />
          </div>
          <div>
            <label className="zk-label">MAX DISCLOSURE</label>
            <select className="zk-select" value={form.max_disclosure_level}
              onChange={(e) => set("max_disclosure_level", parseInt(e.target.value))}>
              <option value={0}>Level 0 — Class only</option>
              <option value={1}>Level 1 — + Component</option>
              <option value={2}>Level 2 — + Attack surface</option>
              <option value={3}>Level 3 — Full PoC summary</option>
            </select>
          </div>
        </div>

        <div className="zk-section-title">SECURE YOUR EXPLOIT</div>
        <div className="border-2 border-zk-border p-5 bg-white">
          <p className="text-sm mb-4">
            Before submitting your PoC, verify the enclave is running trusted code and
            encrypt your exploit so <span className="font-mono font-bold">only the TEE can decrypt it</span> —
            even if the platform host is compromised.
          </p>

          <div className="font-mono text-xs bg-zk-bg p-4 mb-4 overflow-x-auto whitespace-pre">{
`# Install the verification tool (open source)
pip install nitro-verify

# 1. Verify the enclave attestation (AWS hardware signature)
nitro-verify attest https://zdayzk.com/api/v1/enclave/attestation \\
  --pcr0 <expected_code_hash> \\
  --save-pubkey enclave.der

# 2. Encrypt your exploit to the attested enclave
nitro-verify seal ./my-exploit.tar.gz \\
  --pubkey enclave.der \\
  -o exploit.sealed

# 3. Upload exploit.sealed via the marketplace`
          }</div>

          <div className="flex items-center gap-4">
            <a
              href="https://github.com/discordwell/nitro-verify"
              target="_blank"
              rel="noopener noreferrer"
              className="zk-btn-sm no-underline"
            >
              VIEW ON GITHUB
            </a>
            <span className="font-mono text-label text-zk-dim">
              pip install nitro-verify
            </span>
          </div>

          <p className="font-mono text-label text-zk-muted mt-4">
            WHY: THE ATTESTATION IS SIGNED BY AWS HARDWARE, NOT THE HOST.
            PCR0 PROVES THE EXACT CODE RUNNING IN THE ENCLAVE.
            THE PUBLIC KEY IS BOUND TO THE ATTESTATION — MITM IS DETECTABLE.
          </p>
        </div>

        <div className="pt-4">
          <button type="submit" disabled={loading} className="zk-btn-accent disabled:opacity-50">
            {loading ? "SUBMITTING..." : "POST VULNERABILITY"}
          </button>
        </div>
      </form>
    </div>
  );
}
