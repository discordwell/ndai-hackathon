import React from "react";

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Radial gradient background */}
      <div className="absolute inset-0 bg-gradient-radial from-surface-800/60 via-surface-950 to-surface-950" />

      {/* Subtle grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(250,204,21,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(250,204,21,0.3) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Gold orb glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-accent-400/[0.03] rounded-full blur-[120px]" />

      <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-surface-700/60 bg-surface-850/50 backdrop-blur-sm text-xs font-mono text-accent-400 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-pulse-slow" />
          Base Sepolia &middot; TEE-Verified &middot; On-Chain
        </div>

        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
          <span className="text-white">Zero-Day</span>
          <br />
          <span className="bg-gradient-to-r from-accent-300 via-accent-400 to-accent-500 bg-clip-text text-transparent">
            Exchange
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Verified exploits. Fair pricing via Nash bargaining inside hardware enclaves.
          On-chain escrow with sealed zero-knowledge delivery.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <a
            href="#/marketplace"
            className="px-8 py-3.5 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 transition-colors text-sm"
          >
            Browse Marketplace
          </a>
          <a
            href="#/submit"
            className="px-8 py-3.5 border border-surface-600 text-gray-300 font-medium rounded-lg hover:border-accent-500/40 hover:text-white transition-all text-sm"
          >
            Submit a Vulnerability
          </a>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2">
          <div className="w-5 h-8 rounded-full border border-surface-600 flex items-start justify-center p-1">
            <div className="w-1 h-2 bg-accent-400/60 rounded-full animate-bounce" />
          </div>
        </div>
      </div>
    </section>
  );
}
