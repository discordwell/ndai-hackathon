import React from "react";

const signals = [
  {
    title: "TEE-Verified",
    description:
      "Every exploit is tested inside a hardware-isolated AWS Nitro Enclave. COSE-signed attestation proves code integrity. PCR measurements are publicly verifiable.",
    badge: "Nitro Enclaves",
  },
  {
    title: "On-Chain Escrow",
    description:
      "Funds locked in VulnEscrow smart contracts on Base. 10% platform fee. Automatic refund on independent patch discovery. Settlement is trustless.",
    badge: "Base Sepolia",
  },
  {
    title: "Sealed Delivery",
    description:
      "Zero-knowledge transfer via ECIES re-encryption inside the enclave. The platform stores only ciphertext — it never possesses any decryption key.",
    badge: "ECIES P-384",
  },
];

export function TrustSignals() {
  return (
    <section className="py-24 px-6 border-t border-surface-700/30">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Trust Architecture
          </h2>
          <p className="text-gray-400 max-w-xl mx-auto">
            Cryptographic guarantees at every layer. Not trust — verification.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {signals.map((signal) => (
            <div
              key={signal.title}
              className="glass-card p-8 relative overflow-hidden group"
            >
              {/* Top accent bar */}
              <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent-400/40 to-transparent" />

              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-semibold text-white">
                  {signal.title}
                </h3>
                <span className="text-[10px] font-mono text-accent-500 bg-accent-400/10 px-2 py-0.5 rounded border border-accent-400/20">
                  {signal.badge}
                </span>
              </div>
              <p className="text-sm text-gray-400 leading-relaxed">
                {signal.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
