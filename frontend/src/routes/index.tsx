import React, { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { SellerLayout } from "../layouts/SellerLayout";
import { BuyerLayout } from "../layouts/BuyerLayout";
import { RecallLayout } from "../layouts/RecallLayout";
import { PropsLayout } from "../layouts/PropsLayout";
import { SellerDashboard } from "../pages/seller/SellerDashboard";
import { InventionListPage } from "../pages/seller/InventionListPage";
import { InventionCreatePage } from "../pages/seller/InventionCreatePage";
import { SellerAgreementListPage } from "../pages/seller/SellerAgreementListPage";
import { SellerAgreementDetailPage } from "../pages/seller/SellerAgreementDetailPage";
import { BuyerDashboard } from "../pages/buyer/BuyerDashboard";
import { MarketplacePage } from "../pages/buyer/MarketplacePage";
import { BuyerAgreementListPage } from "../pages/buyer/BuyerAgreementListPage";
import { BuyerAgreementDetailPage } from "../pages/buyer/BuyerAgreementDetailPage";
import { SecretCreatePage } from "../pages/recall/SecretCreatePage";
import { SecretListPage } from "../pages/recall/SecretListPage";
import { SecretUsePage } from "../pages/recall/SecretUsePage";
import { AccessLogPage } from "../pages/recall/AccessLogPage";
import { SubmitTranscriptPage } from "../pages/props/SubmitTranscriptPage";
import { TranscriptListPage } from "../pages/props/TranscriptListPage";
import { SummaryPage } from "../pages/props/SummaryPage";
import { AggregationPage } from "../pages/props/AggregationPage";

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash || "#/login");
  useEffect(() => {
    const handler = () => setHash(window.location.hash || "#/login");
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  return hash;
}

export function Router() {
  const hash = useHash();
  const { isAuthenticated, role } = useAuth();
  const path = hash.replace("#", "");

  // Redirect authenticated users away from auth pages
  if (isAuthenticated && (path === "/login" || path === "/register" || path === "/")) {
    window.location.hash = role === "seller" ? "#/seller" : "#/buyer";
    return null;
  }

  // Public routes
  if (path === "/login") return <LoginPage />;
  if (path === "/register") return <RegisterPage />;

  // Recall routes
  if (path === "/recall")
    return <RecallLayout><SecretListPage mode="mine" /></RecallLayout>;
  if (path === "/recall/new")
    return <RecallLayout><SecretCreatePage /></RecallLayout>;
  if (path === "/recall/browse")
    return <RecallLayout><SecretListPage mode="browse" /></RecallLayout>;
  if (path.match(/^\/recall\/[^/]+\/use$/)) {
    const id = path.replace("/recall/", "").replace("/use", "");
    return <RecallLayout><SecretUsePage id={id} /></RecallLayout>;
  }
  if (path.match(/^\/recall\/[^/]+\/log$/)) {
    const id = path.replace("/recall/", "").replace("/log", "");
    return <RecallLayout><AccessLogPage id={id} /></RecallLayout>;
  }

  // Props routes
  if (path === "/props")
    return <PropsLayout><TranscriptListPage /></PropsLayout>;
  if (path === "/props/submit")
    return <PropsLayout><SubmitTranscriptPage /></PropsLayout>;
  if (path === "/props/aggregate")
    return <PropsLayout><AggregationPage /></PropsLayout>;
  if (path.match(/^\/props\/[^/]+\/summary$/)) {
    const id = path.replace("/props/", "").replace("/summary", "");
    return <PropsLayout><SummaryPage id={id} /></PropsLayout>;
  }

  // Seller routes
  if (path === "/seller")
    return (
      <SellerLayout>
        <SellerDashboard />
      </SellerLayout>
    );
  if (path === "/seller/inventions")
    return (
      <SellerLayout>
        <InventionListPage />
      </SellerLayout>
    );
  if (path === "/seller/inventions/new")
    return (
      <SellerLayout>
        <InventionCreatePage />
      </SellerLayout>
    );
  if (path === "/seller/agreements")
    return (
      <SellerLayout>
        <SellerAgreementListPage />
      </SellerLayout>
    );
  if (path.startsWith("/seller/agreements/")) {
    const id = path.replace("/seller/agreements/", "");
    return (
      <SellerLayout>
        <SellerAgreementDetailPage id={id} />
      </SellerLayout>
    );
  }

  // Buyer routes
  if (path === "/buyer")
    return (
      <BuyerLayout>
        <BuyerDashboard />
      </BuyerLayout>
    );
  if (path === "/buyer/marketplace")
    return (
      <BuyerLayout>
        <MarketplacePage />
      </BuyerLayout>
    );
  if (path === "/buyer/agreements")
    return (
      <BuyerLayout>
        <BuyerAgreementListPage />
      </BuyerLayout>
    );
  if (path.startsWith("/buyer/agreements/")) {
    const id = path.replace("/buyer/agreements/", "");
    return (
      <BuyerLayout>
        <BuyerAgreementDetailPage id={id} />
      </BuyerLayout>
    );
  }

  // Fallback — redirect to login
  if (!isAuthenticated) {
    window.location.hash = "#/login";
    return null;
  }

  // Unknown route for authenticated user — go to dashboard
  window.location.hash = role === "seller" ? "#/seller" : "#/buyer";
  return null;
}
