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
    <div className="bg-ndai-700 text-white px-4 py-2 flex items-center gap-6">
      <span className="font-bold text-sm tracking-wide mr-4">TRUSTKIT</span>
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
