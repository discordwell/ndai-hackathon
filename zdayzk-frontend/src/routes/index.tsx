import React from "react";
import { useHash } from "../hooks/useHash";
import { useAuth } from "../contexts/AuthContext";
import { PublicLayout } from "../layouts/PublicLayout";
import { AppLayout } from "../layouts/AppLayout";
import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { DashboardPage } from "../pages/DashboardPage";
import { MarketplacePage } from "../pages/marketplace/MarketplacePage";
import { ListingDetailPage } from "../pages/marketplace/ListingDetailPage";
import { SubmitVulnPage } from "../pages/submit/SubmitVulnPage";
import { DealsListPage } from "../pages/deals/DealsListPage";
import { DealPage } from "../pages/deals/DealPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    window.location.hash = "#/login";
    return null;
  }
  return <>{children}</>;
}

export function Router() {
  const hash = useHash();
  const { isAuthenticated } = useAuth();
  const path = hash.replace(/^#/, "") || "/";

  // Redirect authenticated users away from auth pages
  if (isAuthenticated && (path === "/login" || path === "/register")) {
    window.location.hash = "#/dashboard";
    return null;
  }

  // Public routes
  if (path === "/") return <LandingPage />;
  if (path === "/login") return <PublicLayout><LoginPage /></PublicLayout>;
  if (path === "/register") return <PublicLayout><RegisterPage /></PublicLayout>;

  // Authenticated routes
  if (path === "/dashboard")
    return <RequireAuth><AppLayout><DashboardPage /></AppLayout></RequireAuth>;

  if (path === "/marketplace")
    return <RequireAuth><AppLayout><MarketplacePage /></AppLayout></RequireAuth>;

  const listingMatch = path.match(/^\/marketplace\/([^/]+)$/);
  if (listingMatch)
    return <RequireAuth><AppLayout><ListingDetailPage id={listingMatch[1]} /></AppLayout></RequireAuth>;

  if (path === "/submit")
    return <RequireAuth><AppLayout><SubmitVulnPage /></AppLayout></RequireAuth>;

  if (path === "/deals")
    return <RequireAuth><AppLayout><DealsListPage /></AppLayout></RequireAuth>;

  const dealMatch = path.match(/^\/deals\/([^/]+)$/);
  if (dealMatch)
    return <RequireAuth><AppLayout><DealPage dealId={dealMatch[1]} /></AppLayout></RequireAuth>;

  // 404
  return (
    <PublicLayout>
      <div className="text-center space-y-4">
        <h2 className="text-2xl font-mono text-white/60">404</h2>
        <p className="text-white/40">Page not found.</p>
        <a href="#/" className="text-accent-400 hover:text-accent-300 text-sm underline">Go home</a>
      </div>
    </PublicLayout>
  );
}
