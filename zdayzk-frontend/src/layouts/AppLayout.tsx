import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";

const navItems = [
  { label: "Dashboard", hash: "#/dashboard", icon: GridIcon },
  { label: "Marketplace", hash: "#/marketplace", icon: StoreIcon },
  { label: "Submit", hash: "#/submit", icon: PlusIcon },
  { label: "My Deals", hash: "#/deals", icon: HandshakeIcon },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const currentHash = window.location.hash || "#/";

  return (
    <div className="min-h-screen bg-surface-950 flex">
      {/* Sidebar — desktop */}
      <aside className="hidden lg:flex lg:flex-col w-60 bg-surface-900 border-r border-surface-700/50 shrink-0">
        <div className="px-5 py-5">
          <a
            href="#/"
            className="text-xl font-mono font-bold tracking-wider text-accent-400 hover:text-accent-300 transition-colors"
          >
            zdayzk
          </a>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const active = currentHash.startsWith(item.hash);
            return (
              <a
                key={item.hash}
                href={item.hash}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? "bg-accent-400/10 text-accent-400"
                    : "text-white/60 hover:text-white hover:bg-surface-800"
                }`}
              >
                <item.icon active={active} />
                {item.label}
              </a>
            );
          })}
        </nav>
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        >
          <div className="absolute inset-0 bg-black/60" />
          <aside
            className="relative w-64 h-full bg-surface-900 border-r border-surface-700/50 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 py-5 flex items-center justify-between">
              <a
                href="#/"
                className="text-xl font-mono font-bold tracking-wider text-accent-400"
              >
                zdayzk
              </a>
              <button
                onClick={() => setSidebarOpen(false)}
                className="text-white/60 hover:text-white"
              >
                <CloseIcon />
              </button>
            </div>
            <nav className="flex-1 px-3 py-4 space-y-1">
              {navItems.map((item) => {
                const active = currentHash.startsWith(item.hash);
                return (
                  <a
                    key={item.hash}
                    href={item.hash}
                    onClick={() => setSidebarOpen(false)}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      active
                        ? "bg-accent-400/10 text-accent-400"
                        : "text-white/60 hover:text-white hover:bg-surface-800"
                    }`}
                  >
                    <item.icon active={active} />
                    {item.label}
                  </a>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top nav */}
        <header className="h-14 bg-surface-900 border-b border-surface-700/50 flex items-center px-4 gap-4 shrink-0">
          {/* Mobile menu button */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden text-white/60 hover:text-white"
          >
            <MenuIcon />
          </button>

          {/* Mobile logo */}
          <a
            href="#/"
            className="lg:hidden text-lg font-mono font-bold tracking-wider text-accent-400"
          >
            zdayzk
          </a>

          {/* Desktop nav links */}
          <nav className="hidden lg:flex items-center gap-1">
            {navItems.map((item) => {
              const active = currentHash.startsWith(item.hash);
              return (
                <a
                  key={item.hash}
                  href={item.hash}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    active
                      ? "text-accent-400"
                      : "text-white/60 hover:text-white"
                  }`}
                >
                  {item.label}
                </a>
              );
            })}
          </nav>

          <div className="flex-1" />

          {/* Wallet placeholder */}
          <button className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-800 border border-surface-700/50 text-sm text-white/60 hover:text-white transition-colors">
            <WalletIcon />
            <span>Connect</span>
          </button>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-white/80 hover:text-white hover:bg-surface-800 transition-colors"
            >
              <div className="w-7 h-7 rounded-full bg-accent-400/20 flex items-center justify-center text-accent-400 text-xs font-bold">
                {(user?.display_name || user?.email || "U")[0].toUpperCase()}
              </div>
              <span className="hidden sm:inline max-w-[120px] truncate">
                {user?.display_name || user?.email || "User"}
              </span>
            </button>
            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-surface-800 border border-surface-700/50 rounded-lg shadow-xl py-1 z-50">
                <div className="px-3 py-2 text-xs text-white/40 border-b border-surface-700/50 truncate">
                  {user?.email}
                </div>
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    logout();
                  }}
                  className="w-full text-left px-3 py-2 text-sm text-danger-400 hover:bg-surface-700/50 transition-colors"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

/* ---------- Inline SVG icons ---------- */

function GridIcon({ active }: { active: boolean }) {
  return (
    <svg
      className={`w-4 h-4 ${active ? "text-accent-400" : "text-white/40"}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
      />
    </svg>
  );
}

function StoreIcon({ active }: { active: boolean }) {
  return (
    <svg
      className={`w-4 h-4 ${active ? "text-accent-400" : "text-white/40"}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 3h18l-2 9H5L3 3zm0 0l-1-1m6 16a1 1 0 102 0 1 1 0 00-2 0zm8 0a1 1 0 102 0 1 1 0 00-2 0z"
      />
    </svg>
  );
}

function PlusIcon({ active }: { active: boolean }) {
  return (
    <svg
      className={`w-4 h-4 ${active ? "text-accent-400" : "text-white/40"}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 4v16m8-8H4"
      />
    </svg>
  );
}

function HandshakeIcon({ active }: { active: boolean }) {
  return (
    <svg
      className={`w-4 h-4 ${active ? "text-accent-400" : "text-white/40"}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg
      className="w-5 h-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 6h16M4 12h16M4 18h16"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      className="w-5 h-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  );
}

function WalletIcon() {
  return (
    <svg
      className="w-4 h-4"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
      />
    </svg>
  );
}
