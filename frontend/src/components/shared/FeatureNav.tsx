import React, { useState, useEffect } from "react";

const FEATURES = [
  { label: "NDAI Agreements", href: "#/seller", prefixes: ["#/seller", "#/buyer"] },
  { label: "Conditional Recall", href: "#/recall", prefixes: ["#/recall"] },
  { label: "Props", href: "#/props", prefixes: ["#/props"] },
  { label: "Poker", href: "#/poker", prefixes: ["#/poker"] },
  { label: "Zero-Day Market", href: "#/vuln", prefixes: ["#/vuln"] },
  { label: "0day (ZK)", href: "#/zk", prefixes: ["#/zk"] },
];

export function FeatureNav() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const handler = () => setHash(window.location.hash);
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  return (
    <div className="bg-gradient-to-r from-ndai-800 to-ndai-700 text-white px-4 py-2 flex items-center gap-6">
      <div className="flex items-center gap-2 mr-4">
        <svg className="w-5 h-5 text-ndai-200" viewBox="0 0 48 48" fill="none">
          <path d="M24 4L6 12v12c0 11 8 18 18 22 10-4 18-11 18-22V12L24 4z" fill="currentColor" />
          <circle cx="24" cy="22" r="3.5" fill="none" stroke="white" strokeWidth="1.5" />
          <rect x="22.75" y="25" width="2.5" height="4" rx="0.75" fill="white" />
        </svg>
        <span className="font-bold text-sm tracking-wide">TRUSTKIT</span>
      </div>
      {FEATURES.map((f) => {
        const active = f.prefixes.some((p) => hash.startsWith(p));
        return (
          <a
            key={f.href}
            href={f.href}
            className={`text-sm px-3 py-1 rounded transition-colors ${
              active ? "bg-white/20 font-medium" : "text-white/70 hover:text-white hover:bg-white/10"
            }`}
          >
            {f.label}
          </a>
        );
      })}
    </div>
  );
}
