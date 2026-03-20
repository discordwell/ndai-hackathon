import React from "react";
import { useAuth } from "../../contexts/AuthContext";

interface NavItem {
  label: string;
  href: string;
}

const SELLER_NAV: NavItem[] = [
  { label: "Dashboard", href: "#/seller" },
  { label: "My Inventions", href: "#/seller/inventions" },
  { label: "Agreements", href: "#/seller/agreements" },
];

const BUYER_NAV: NavItem[] = [
  { label: "Dashboard", href: "#/buyer" },
  { label: "Marketplace", href: "#/buyer/marketplace" },
  { label: "Agreements", href: "#/buyer/agreements" },
];

const RECALL_NAV: NavItem[] = [
  { label: "My Secrets", href: "#/recall" },
  { label: "Upload Secret", href: "#/recall/new" },
  { label: "Browse Secrets", href: "#/recall/browse" },
];

const PROPS_NAV: NavItem[] = [
  { label: "My Transcripts", href: "#/props" },
  { label: "Submit Transcript", href: "#/props/submit" },
  { label: "Cross-Team Analysis", href: "#/props/aggregate" },
];

function getNav(hash: string, role: string | null): { nav: NavItem[]; title: string; subtitle: string } {
  if (hash.startsWith("#/recall")) return { nav: RECALL_NAV, title: "Recall", subtitle: "Credential Proxy" };
  if (hash.startsWith("#/props")) return { nav: PROPS_NAV, title: "Props", subtitle: "Transcript Intelligence" };
  if (role === "buyer") return { nav: BUYER_NAV, title: "NDAI", subtitle: "Investor Portal" };
  return { nav: SELLER_NAV, title: "NDAI", subtitle: "Inventor Portal" };
}

export function Sidebar() {
  const { role, logout } = useAuth();
  const hash = window.location.hash;
  const { nav, title, subtitle } = getNav(hash, role);

  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-screen flex flex-col">
      <div className="p-6">
        <h1 className="text-xl font-bold text-ndai-700">{title}</h1>
        <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
      </div>
      <nav className="flex-1 px-3">
        {nav.map((item) => {
          const active = hash === item.href || (item.href !== nav[0].href && hash.startsWith(item.href));
          return (
            <a
              key={item.href}
              href={item.href}
              className={`block px-3 py-2 rounded-lg mb-1 text-sm transition-colors ${
                active ? "bg-ndai-50 text-ndai-700 font-medium" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {item.label}
            </a>
          );
        })}
      </nav>
      <div className="p-3 border-t border-gray-100">
        <button
          onClick={() => { logout(); window.location.hash = "#/login"; }}
          className="w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg text-left"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
