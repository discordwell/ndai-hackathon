import React, { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { MarketplaceLayout } from "../layouts/MarketplaceLayout";
import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { BrowsePage } from "../pages/marketplace/BrowsePage";
import { VulnDetailPage } from "../pages/marketplace/VulnDetailPage";
import { RFPDetailPage } from "../pages/marketplace/RFPDetailPage";
import { SubmitVulnPage } from "../pages/sell/SubmitVulnPage";
import { MyListingsPage } from "../pages/sell/MyListingsPage";
import { ProposalPage } from "../pages/sell/ProposalPage";
import { PostRFPPage } from "../pages/buy/PostRFPPage";
import { MyRFPsPage } from "../pages/buy/MyRFPsPage";
import { RFPManagePage } from "../pages/buy/RFPManagePage";
import { DealsListPage } from "../pages/deals/DealsListPage";
import { DealPage } from "../pages/deals/DealPage";
import { InboxPage } from "../pages/messages/InboxPage";
import { ConversationPage } from "../pages/messages/ConversationPage";
import { NewConversationPage } from "../pages/messages/NewConversationPage";
import { TargetsPage } from "../pages/targets/TargetsPage";
import { TargetDetailPage } from "../pages/targets/TargetDetailPage";
import { MyProposalsPage } from "../pages/proposals/MyProposalsPage";
import { ProposalPage } from "../pages/proposals/ProposalPage";
import { ProposalStatusPage } from "../pages/proposals/ProposalStatusPage";

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const handler = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  return hash;
}

export function Router() {
  const hash = useHash();
  const { isAuthenticated } = useAuth();
  const path = hash.replace("#", "");

  // Public routes
  if (path === "/" || path === "") return <LandingPage />;
  if (path === "/login") return <LoginPage />;
  if (path === "/register") return <RegisterPage />;

  // Redirect unauthenticated users
  if (!isAuthenticated) {
    window.location.hash = "#/login";
    return null;
  }

  // Authenticated routes — all wrapped in MarketplaceLayout
  let content: React.ReactNode = null;

  // Browse
  if (path === "/browse") content = <BrowsePage />;

  // Vuln detail
  const vulnMatch = path.match(/^\/browse\/vuln\/(.+)$/);
  if (vulnMatch) content = <VulnDetailPage id={vulnMatch[1]} />;

  // RFP detail (marketplace view)
  const rfpBrowseMatch = path.match(/^\/browse\/rfp\/(.+)$/);
  if (rfpBrowseMatch) content = <RFPDetailPage id={rfpBrowseMatch[1]} />;

  // Sell
  if (path === "/sell") content = <MyListingsPage />;
  if (path === "/sell/new") content = <SubmitVulnPage />;
  const proposeMatch = path.match(/^\/sell\/propose\/(.+)$/);
  if (proposeMatch) content = <ProposalPage rfpId={proposeMatch[1]} />;

  // Buy
  if (path === "/buy") content = <MyRFPsPage />;
  if (path === "/buy/new") content = <PostRFPPage />;
  const rfpManageMatch = path.match(/^\/buy\/rfp\/(.+)$/);
  if (rfpManageMatch) content = <RFPManagePage id={rfpManageMatch[1]} />;

  // Deals
  if (path === "/deals") content = <DealsListPage />;
  const dealMatch = path.match(/^\/deals\/(.+)$/);
  if (dealMatch) content = <DealPage id={dealMatch[1]} />;

  // Messages
  if (path === "/messages") content = <InboxPage />;
  if (path === "/messages/new") content = <NewConversationPage />;
  const msgDealMatch = path.match(/^\/messages\/deal\/(.+)$/);
  if (msgDealMatch) content = <ConversationPage conversationId={msgDealMatch[1]} />;
  const msgMatch = path.match(/^\/messages\/([^/]+)$/);
  if (msgMatch && !path.startsWith("/messages/new") && !path.startsWith("/messages/deal/")) content = <ConversationPage conversationId={msgMatch[1]} />;

  // Targets
  if (path === "/targets") content = <TargetsPage />;
  const targetMatch = path.match(/^\/targets\/(.+)$/);
  if (targetMatch) content = <TargetDetailPage targetId={targetMatch[1]} />;

  // Proposals
  if (path === "/proposals") content = <MyProposalsPage />;
  if (path === "/proposals/new") {
    const params = new URLSearchParams(window.location.hash.split("?")[1] || "");
    const targetId = params.get("target");
    if (targetId) content = <ProposalPage targetId={targetId} />;
    else content = <TargetsPage />;
  }
  const proposalMatch = path.match(/^\/proposals\/([^/]+)$/);
  if (proposalMatch && path !== "/proposals/new") content = <ProposalStatusPage proposalId={proposalMatch[1]} />;

  if (content) {
    return <MarketplaceLayout>{content}</MarketplaceLayout>;
  }

  // Unknown route — go to browse
  window.location.hash = "#/browse";
  return null;
}
