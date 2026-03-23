/**
 * ZK-authenticated vulnerability marketplace API client.
 */
import { zkGet, zkPost } from "./zkClient";

// ── Request types ──

export interface ZKVulnCreateRequest {
  target_software: string;
  target_version: string;
  vulnerability_class: string;
  impact_type: string;
  affected_component?: string;
  anonymized_summary?: string;
  cvss_self_assessed: number;
  asking_price_eth: number;
  discovery_date: string;
  patch_status?: string;
  exclusivity?: string;
  serious_customers_only?: boolean;
}

export interface ZKAgreementCreateRequest {
  vulnerability_id: string;
}

export interface ZKWalletConnectRequest {
  eth_address: string;
}

// ── Response types ──

export interface ZKVulnResponse {
  id: string;
  seller_pubkey: string;
  target_software: string;
  target_version: string;
  vulnerability_class: string;
  impact_type: string;
  cvss_self_assessed: number;
  asking_price_eth: number;
  patch_status: string;
  exclusivity: string;
  serious_customers_only: boolean;
  status: string;
  created_at: string;
}

export interface ZKVulnListingResponse {
  id: string;
  target_software: string;
  target_version: string;
  vulnerability_class: string;
  impact_type: string;
  cvss_self_assessed: number;
  asking_price_eth: number;
  anonymized_summary?: string;
  patch_status: string;
  exclusivity: string;
  serious_customers_only: boolean;
  status: string;
  created_at: string;
}

export interface ZKAgreementResponse {
  id: string;
  vulnerability_id: string;
  seller_pubkey: string;
  buyer_pubkey: string;
  status: string;
  escrow_address?: string;
  seller_eth_address?: string;
  buyer_eth_address?: string;
  created_at: string;
}

export interface ZKOutcomeResponse {
  outcome: string;
  final_price?: number;
  negotiation_rounds?: number;
}

// ── API functions ──

export function createVuln(data: ZKVulnCreateRequest) {
  return zkPost<ZKVulnResponse>("/zk-vulns/", data);
}

export function listMyVulns() {
  return zkGet<ZKVulnResponse[]>("/zk-vulns/");
}

export function listVulnListings() {
  return zkGet<ZKVulnListingResponse[]>("/zk-vulns/listings");
}

export function createAgreement(data: ZKAgreementCreateRequest) {
  return zkPost<ZKAgreementResponse>("/zk-vulns/agreements", data);
}

export function listMyAgreements() {
  return zkGet<ZKAgreementResponse[]>("/zk-vulns/agreements");
}

export function getAgreement(id: string) {
  return zkGet<ZKAgreementResponse>(`/zk-vulns/agreements/${id}`);
}

export function connectWallet(agreementId: string, data: ZKWalletConnectRequest) {
  return zkPost<ZKAgreementResponse>(`/zk-vulns/agreements/${agreementId}/wallet`, data);
}

export function startNegotiation(agreementId: string) {
  return zkPost<{ status: string }>(`/zk-vulns/negotiations/${agreementId}/start`);
}
