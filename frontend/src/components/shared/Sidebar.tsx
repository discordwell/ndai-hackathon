import React, { useState, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

function Icon({ d }: { d: string }) {
  return (
    <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  );
}

const SELLER_NAV: NavItem[] = [
  { label: "Dashboard", href: "#/seller", icon: <Icon d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" /> },
  { label: "My Inventions", href: "#/seller/inventions", icon: <Icon d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /> },
  { label: "Agreements", href: "#/seller/agreements", icon: <Icon d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /> },
];

const BUYER_NAV: NavItem[] = [
  { label: "Dashboard", href: "#/buyer", icon: <Icon d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" /> },
  { label: "Marketplace", href: "#/buyer/marketplace", icon: <Icon d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /> },
  { label: "Agreements", href: "#/buyer/agreements", icon: <Icon d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /> },
];

const RECALL_NAV: NavItem[] = [
  { label: "My Secrets", href: "#/recall", icon: <Icon d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /> },
  { label: "Upload Secret", href: "#/recall/new", icon: <Icon d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /> },
  { label: "Browse Secrets", href: "#/recall/browse", icon: <Icon d="M4 6h16M4 10h16M4 14h16M4 18h16" /> },
];

const PROPS_NAV: NavItem[] = [
  { label: "My Transcripts", href: "#/props", icon: <Icon d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /> },
  { label: "Submit Transcript", href: "#/props/submit", icon: <Icon d="M12 6v6m0 0v6m0-6h6m-6 0H6" /> },
  { label: "Cross-Team Analysis", href: "#/props/aggregate", icon: <Icon d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /> },
];

const POKER_NAV: NavItem[] = [
  { label: "Lobby", href: "#/poker", icon: <Icon d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" /> },
  { label: "Hand History", href: "#/poker/history", icon: <Icon d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /> },
];

function getNav(hash: string, role: string | null): { nav: NavItem[]; title: string; subtitle: string } {
  if (hash.startsWith("#/recall")) return { nav: RECALL_NAV, title: "Recall", subtitle: "Credential Proxy" };
  if (hash.startsWith("#/props")) return { nav: PROPS_NAV, title: "Props", subtitle: "Transcript Intelligence" };
  if (hash.startsWith("#/poker")) return { nav: POKER_NAV, title: "Poker", subtitle: "Texas Hold'em" };
  if (role === "buyer") return { nav: BUYER_NAV, title: "NDAI", subtitle: "Investor Portal" };
  return { nav: SELLER_NAV, title: "NDAI", subtitle: "Inventor Portal" };
}

export function Sidebar() {
  const { role, displayName, logout } = useAuth();
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const handler = () => setHash(window.location.hash);
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  const { nav, title, subtitle } = getNav(hash, role);

  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-screen flex flex-col">
      <div className="p-6">
        <div className="flex items-center gap-2">
          <svg className="w-6 h-6 text-ndai-600" viewBox="0 0 48 48" fill="none">
            <path d="M24 4L6 12v12c0 11 8 18 18 22 10-4 18-11 18-22V12L24 4z" fill="currentColor" />
            <circle cx="24" cy="22" r="3.5" fill="none" stroke="white" strokeWidth="1.5" />
            <rect x="22.75" y="25" width="2.5" height="4" rx="0.75" fill="white" />
          </svg>
          <div>
            <h1 className="text-lg font-bold text-ndai-700 leading-tight">{title}</h1>
            <p className="text-xs text-gray-500">{subtitle}</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-3">
        {nav.map((item) => {
          const active = hash === item.href || (item.href !== nav[0].href && hash.startsWith(item.href));
          return (
            <a
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg mb-1 text-sm transition-colors ${
                active ? "bg-ndai-50 text-ndai-700 font-medium" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {item.icon}
              {item.label}
            </a>
          );
        })}
      </nav>
      <div className="p-3 border-t border-gray-100">
        {displayName && (
          <div className="px-3 py-1.5 text-xs text-gray-400 truncate">{displayName}</div>
        )}
        <button
          onClick={() => { logout(); window.location.hash = "#/login"; }}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg text-left"
        >
          <Icon d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
