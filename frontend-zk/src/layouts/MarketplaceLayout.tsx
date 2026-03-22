import React from "react";
import { useAuth } from "../contexts/AuthContext";

const NAV_ITEMS = [
  { label: "BROWSE", hash: "#/browse" },
  { label: "SELL", hash: "#/sell" },
  { label: "BUY", hash: "#/buy" },
  { label: "DEALS", hash: "#/deals" },
];

export function MarketplaceLayout({ children }: { children: React.ReactNode }) {
  const { logout } = useAuth();
  const currentHash = window.location.hash;

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <header className="border-b-3 border-zk-border bg-white">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between h-14">
          <a
            href="#/"
            className="font-mono font-extrabold text-xl tracking-tighter no-underline text-zk-text hover:text-zk-text"
          >
            ZDAYZK
          </a>

          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const active = currentHash.startsWith(item.hash);
              return (
                <a
                  key={item.hash}
                  href={item.hash}
                  className={`px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider no-underline
                    ${active
                      ? "bg-zk-border text-white"
                      : "text-zk-text hover:bg-zk-bg"
                    }`}
                >
                  {item.label}
                </a>
              );
            })}
            <div className="w-px h-6 bg-zk-border mx-2" />
            <button
              onClick={logout}
              className="px-3 py-1.5 font-mono text-xs font-bold uppercase tracking-wider
                         text-zk-muted hover:text-zk-accent"
            >
              EXIT
            </button>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t-2 border-zk-border mt-16">
        <div className="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
          <span className="font-mono text-label text-zk-dim">
            VERIFICATION: AWS NITRO ENCLAVES / SETTLEMENT: BASE SEPOLIA / FEE: 10%
          </span>
          <span className="font-mono text-label text-zk-dim">
            ZDAYZK.COM
          </span>
        </div>
      </footer>
    </div>
  );
}
