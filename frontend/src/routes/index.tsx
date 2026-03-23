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
import { InventionDetailPage } from "../pages/seller/InventionDetailPage";
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
import { PokerLayout } from "../layouts/PokerLayout";
import { PokerTableLayout } from "../layouts/PokerTableLayout";
import { PokerLobbyPage } from "../pages/poker/PokerLobbyPage";
import { PokerTablePage } from "../pages/poker/PokerTablePage";
import { PokerHistoryPage } from "../pages/poker/PokerHistoryPage";
import { VulnLayout } from "../layouts/VulnLayout";
import { VulnMarketplacePage } from "../pages/vuln/VulnMarketplacePage";
import { VulnSubmitPage } from "../pages/vuln/VulnSubmitPage";
import { VulnListPage } from "../pages/vuln/VulnListPage";
import { VulnDealPage } from "../pages/vuln/VulnDealPage";
import { VulnDemoPage } from "../pages/vuln/VulnDemoPage";
import { ZKLayout } from "../layouts/ZKLayout";
import { ZKAuthPage } from "../pages/zk/ZKAuthPage";
import { ZKMarketplacePage } from "../pages/zk/ZKMarketplacePage";
import { ZKSubmitPage } from "../pages/zk/ZKSubmitPage";
import { ZKBountyCreatePage } from "../pages/zk/ZKBountyCreatePage";
import { ZKMyListingsPage } from "../pages/zk/ZKMyListingsPage";
import { ZKDealPage } from "../pages/zk/ZKDealPage";
import { ZKDealsListPage } from "../pages/zk/ZKDealsListPage";
import { ZKIdentityPage } from "../pages/zk/ZKIdentityPage";
import { ZKAuctionPage } from "../pages/zk/ZKAuctionPage";
import { ZKAuctionCreatePage } from "../pages/zk/ZKAuctionCreatePage";
import { NotFoundPage } from "../pages/NotFoundPage";

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
  if (path.match(/^\/seller\/inventions\/[^/]+$/) && path !== "/seller/inventions/new") {
    const id = path.replace("/seller/inventions/", "");
    return (
      <SellerLayout>
        <InventionDetailPage id={id} />
      </SellerLayout>
    );
  }
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

  // Poker routes
  if (path === "/poker") return <PokerLayout><PokerLobbyPage /></PokerLayout>;
  if (path === "/poker/history") return <PokerLayout><PokerHistoryPage /></PokerLayout>;
  const pokerTableMatch = path.match(/^\/poker\/table\/([^/]+)$/);
  if (pokerTableMatch) return <PokerTableLayout><PokerTablePage tableId={pokerTableMatch[1]} /></PokerTableLayout>;

  // ZK 0day marketplace routes (separate auth system)
  if (path === "/zk/auth") return <ZKAuthPage />;
  if (path === "/zk") return <ZKLayout><ZKMarketplacePage /></ZKLayout>;
  if (path === "/zk/submit") return <ZKLayout><ZKSubmitPage /></ZKLayout>;
  if (path === "/zk/bounty/new") return <ZKLayout><ZKBountyCreatePage /></ZKLayout>;
  if (path === "/zk/mine") return <ZKLayout><ZKMyListingsPage /></ZKLayout>;
  if (path === "/zk/deals") return <ZKLayout><ZKDealsListPage /></ZKLayout>;
  if (path === "/zk/identity") return <ZKLayout><ZKIdentityPage /></ZKLayout>;
  if (path === "/zk/auctions/new") return <ZKLayout><ZKAuctionCreatePage /></ZKLayout>;
  const zkAuctionMatch = path.match(/^\/zk\/auctions\/([^/]+)$/);
  if (zkAuctionMatch) return <ZKLayout><ZKAuctionPage auctionId={zkAuctionMatch[1]} /></ZKLayout>;
  const zkDealMatch = path.match(/^\/zk\/deals\/([^/]+)$/);
  if (zkDealMatch) return <ZKLayout><ZKDealPage dealId={zkDealMatch[1]} /></ZKLayout>;

  // Vuln marketplace routes
  if (path === "/vuln") return <VulnLayout><VulnMarketplacePage /></VulnLayout>;
  if (path === "/vuln/submit") return <VulnLayout><VulnSubmitPage /></VulnLayout>;
  if (path === "/vuln/mine") return <VulnLayout><VulnListPage /></VulnLayout>;
  const vulnDemoMatch = path.match(/^\/vuln\/demo\/([^/]+)$/);
  if (vulnDemoMatch) return <VulnLayout><VulnDemoPage dealId={vulnDemoMatch[1]} /></VulnLayout>;
  const vulnDealMatch = path.match(/^\/vuln\/deals\/([^/]+)$/);
  if (vulnDealMatch) return <VulnLayout><VulnDealPage dealId={vulnDealMatch[1]} /></VulnLayout>;

  // Fallback — redirect to login
  if (!isAuthenticated) {
    window.location.hash = "#/login";
    return null;
  }

  // Unknown route for authenticated user — show 404
  return <NotFoundPage />;
}
