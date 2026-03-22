import React from "react";

const steps = [
  {
    number: "01",
    title: "Submit or Browse",
    description:
      "Security researchers submit vulnerabilities with encrypted PoC. Buyers browse anonymized listings — target software, CVSS severity, and impact type visible. Identity stays hidden.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
    ),
  },
  {
    number: "02",
    title: "TEE Verifies & AI Negotiates",
    description:
      "Inside an AWS Nitro Enclave, capability oracles verify the exploit is real. AI agents negotiate a fair price using bilateral Nash bargaining. No human bias.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
  },
  {
    number: "03",
    title: "On-Chain Escrow & Sealed Delivery",
    description:
      "Funds locked in VulnEscrow on Base. 10% platform fee enforced on-chain. Exploit encrypted via ECIES — the platform never possesses the decryption key. Only the buyer can decrypt.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
      </svg>
    ),
  },
];

export function HowItWorks() {
  return (
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            How It Works
          </h2>
          <p className="text-gray-400 max-w-xl mx-auto">
            Three steps from discovery to delivery. Every stage is cryptographically verifiable.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {steps.map((step) => (
            <div
              key={step.number}
              className="glass-card p-8 group hover:border-accent-500/30 transition-all duration-300"
            >
              <div className="flex items-center gap-3 mb-5">
                <span className="text-xs font-mono text-accent-500 bg-accent-400/10 px-2.5 py-1 rounded">
                  {step.number}
                </span>
                <div className="text-accent-400 opacity-60 group-hover:opacity-100 transition-opacity">
                  {step.icon}
                </div>
              </div>
              <h3 className="text-lg font-semibold text-white mb-3">
                {step.title}
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
