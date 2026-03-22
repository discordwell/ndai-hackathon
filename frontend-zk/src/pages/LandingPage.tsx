import React from "react";
import { useAuth } from "../contexts/AuthContext";

export function LandingPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <div className="border-b-3 border-zk-border">
        <div className="max-w-6xl mx-auto px-6 py-20">
          <div className="mb-4">
            <span className="zk-stamp border-zk-accent text-zk-accent text-xs">
              VERIFIED MARKETPLACE
            </span>
          </div>
          <h1 className="font-mono font-extrabold text-display text-zk-text leading-none mb-6">
            ZDAYZK
          </h1>
          <p className="font-mono text-subhead text-zk-muted max-w-xl leading-relaxed">
            Two-sided zero-day vulnerability marketplace.
            TEE-verified exploits. Nash-bargained pricing.
            On-chain settlement. Zero-knowledge delivery.
          </p>
        </div>
      </div>

      {/* Two columns: SELL / BUY */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-2">
        {/* SELL column */}
        <div className="border-b-3 md:border-b-0 md:border-r-3 border-zk-border">
          <div className="max-w-md mx-auto px-6 py-16 md:ml-auto md:mr-12">
            <h2 className="font-mono text-headline mb-6">SELL</h2>
            <div className="space-y-4 mb-8">
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">01</span>
                <span className="text-sm">Post your vulnerability with target spec and encrypted PoC</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">02</span>
                <span className="text-sm">TEE enclave verifies exploit via capability oracles</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">03</span>
                <span className="text-sm">AI agents negotiate price via bilateral Nash bargaining</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">04</span>
                <span className="text-sm">Receive 90% of deal price via on-chain settlement</span>
              </div>
            </div>
            <a href={isAuthenticated ? "#/sell/new" : "#/register"} className="zk-btn no-underline">
              POST VULNERABILITY
            </a>
          </div>
        </div>

        {/* BUY column */}
        <div>
          <div className="max-w-md mx-auto px-6 py-16 md:mr-auto md:ml-12">
            <h2 className="font-mono text-headline mb-6">BUY</h2>
            <div className="space-y-4 mb-8">
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">01</span>
                <span className="text-sm">Post an RFP with target, threat model, and acceptance criteria</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">02</span>
                <span className="text-sm">Optionally attach custom patches for overlap detection</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">03</span>
                <span className="text-sm">Receive verified proposals from researchers</span>
              </div>
              <div className="flex gap-3">
                <span className="font-mono text-sm text-zk-accent font-bold w-6 shrink-0">04</span>
                <span className="text-sm">Accept and receive exploit via sealed zero-knowledge delivery</span>
              </div>
            </div>
            <a href={isAuthenticated ? "#/buy/new" : "#/register"} className="zk-btn-accent no-underline">
              POST RFP
            </a>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="border-t-3 border-zk-border bg-white">
        <div className="max-w-6xl mx-auto px-6 py-6 grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { label: "ACTIVE LISTINGS", value: "--" },
            { label: "OPEN RFPS", value: "--" },
            { label: "DEALS CLOSED", value: "--" },
            { label: "PLATFORM FEE", value: "10%" },
          ].map((stat) => (
            <div key={stat.label}>
              <div className="font-mono text-2xl font-bold">{stat.value}</div>
              <div className="font-mono text-label text-zk-dim mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t-2 border-zk-border">
        <div className="max-w-6xl mx-auto px-6 py-4 flex flex-col md:flex-row justify-between gap-2">
          <span className="font-mono text-label text-zk-dim">
            VERIFICATION: AWS NITRO ENCLAVES / SETTLEMENT: BASE SEPOLIA
          </span>
          <span className="font-mono text-label text-zk-dim">
            {isAuthenticated ? (
              <a href="#/browse" className="text-zk-dim hover:text-zk-accent no-underline">
                ENTER MARKETPLACE &rarr;
              </a>
            ) : (
              <a href="#/login" className="text-zk-dim hover:text-zk-accent no-underline">
                LOGIN &rarr;
              </a>
            )}
          </span>
        </div>
      </footer>
    </div>
  );
}
