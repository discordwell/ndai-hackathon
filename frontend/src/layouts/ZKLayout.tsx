import React from "react";
import { useZKAuth } from "../contexts/ZKAuthContext";

const NAV_LINKS = [
  { label: "Marketplace", hash: "#/zk" },
  { label: "Submit", hash: "#/zk/submit" },
  { label: "Bounties", hash: "#/zk/bounty/new" },
  { label: "My Listings", hash: "#/zk/mine" },
  { label: "Deals", hash: "#/zk/deals" },
  { label: "Identity", hash: "#/zk/identity" },
];

export function ZKLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, publicKeyHex, logout } = useZKAuth();

  if (!isAuthenticated) {
    window.location.hash = "#/zk/auth";
    return null;
  }

  const currentHash = window.location.hash || "#/zk";

  return (
    <div className="min-h-screen bg-void-950 text-void-50">
      {/* Top bar */}
      <header className="border-b border-void-700 bg-void-900">
        <div className="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
          {/* Branding */}
          <a
            href="#/zk"
            className="text-lg font-bold tracking-wider text-void-50 hover:text-void-200"
          >
            0DAY
          </a>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map((link) => {
              const isActive =
                currentHash === link.hash ||
                (link.hash === "#/zk" && currentHash === "#/zk");
              return (
                <a
                  key={link.hash}
                  href={link.hash}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                    isActive
                      ? "bg-void-700 text-void-50"
                      : "text-void-300 hover:text-void-100 hover:bg-void-800"
                  }`}
                >
                  {link.label}
                </a>
              );
            })}
          </nav>

          {/* Pubkey + Logout */}
          <div className="flex items-center gap-3">
            {publicKeyHex && (
              <span className="text-xs font-mono text-void-400">
                {publicKeyHex.slice(0, 8)}...{publicKeyHex.slice(-8)}
              </span>
            )}
            <button
              onClick={() => {
                logout();
                window.location.hash = "#/zk/auth";
              }}
              className="px-3 py-1 text-xs font-medium text-void-300 hover:text-red-400 border border-void-600 rounded hover:border-red-500 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
