import React from "react";

export function Footer() {
  return (
    <footer className="border-t border-surface-700/30 py-12 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold tracking-tight">
              <span className="text-white">zday</span>
              <span className="text-accent-400">zk</span>
            </span>
            <span className="text-xs text-gray-500 border-l border-surface-700 pl-3">
              Zero-Day Marketplace
            </span>
          </div>

          <div className="flex items-center gap-6 text-xs text-gray-500">
            <a href="#/login" className="hover:text-gray-300 transition-colors">
              Sign In
            </a>
            <a href="#/register" className="hover:text-gray-300 transition-colors">
              Register
            </a>
            <span className="font-mono text-gray-600">
              Base Sepolia
            </span>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-surface-700/20 text-center">
          <p className="text-[11px] text-gray-600 font-mono">
            Powered by NDAI &middot; TEE-verified bilateral Nash bargaining &middot; On-chain escrow
          </p>
        </div>
      </div>
    </footer>
  );
}
