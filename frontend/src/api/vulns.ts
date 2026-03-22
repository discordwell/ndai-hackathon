import { get, post } from "./client";

export interface VulnCreateRequest {
  target_software: string;
  target_version: string;
  vulnerability_class: string;
  impact_type: string;
  affected_component?: string;
  anonymized_summary?: string;
  cvss_self_assessed: number;
  discovery_date: string;
  patch_status?: string;
  exclusivity?: string;
  embargo_days?: number;
  outside_option_value?: number;
  max_disclosure_level?: number;
  software_category?: string;
}

export interface VulnResponse {
  id: string;
  target_software: string;
  target_version: string;
  vulnerability_class: string;
  impact_type: string;
  cvss_self_assessed: number;
  patch_status: string;
  exclusivity: string;
  status: string;
}

export interface VulnListingResponse {
  id: string;
  target_software: string;
  vulnerability_class: string;
  impact_type: string;
  patch_status: string;
  exclusivity: string;
  anonymized_summary: string | null;
  cvss_self_assessed: number;
}

export interface VulnAgreementCreateRequest {
  vulnerability_id: string;
  budget_cap: number;
}

export interface VulnAgreementResponse {
  id: string;
  vulnerability_id: string;
  seller_id: string;
  buyer_id: string;
  status: string;
  alpha_0: number | null;
  budget_cap: number | null;
}

export interface VulnOutcomeResponse {
  outcome: string;
  final_price: number | null;
  disclosure_level: number | null;
  reason: string | null;
  negotiation_rounds: number | null;
}

// Vulnerability CRUD
export function createVuln(data: VulnCreateRequest): Promise<VulnResponse> {
  return post<VulnResponse>("/vulns/", data);
}

export function listVulns(): Promise<VulnResponse[]> {
  return get<VulnResponse[]>("/vulns/");
}

export function listVulnListings(): Promise<VulnListingResponse[]> {
  return get<VulnListingResponse[]>("/vulns/listings");
}

export function getVuln(id: string): Promise<VulnResponse> {
  return get<VulnResponse>(`/vulns/${id}`);
}

// Agreements
export function createVulnAgreement(data: VulnAgreementCreateRequest): Promise<VulnAgreementResponse> {
  return post<VulnAgreementResponse>("/vulns/agreements", data);
}

export function listVulnAgreements(): Promise<VulnAgreementResponse[]> {
  return get<VulnAgreementResponse[]>("/vulns/agreements");
}

export function getVulnAgreement(id: string): Promise<VulnAgreementResponse> {
  return get<VulnAgreementResponse>(`/vulns/agreements/${id}`);
}

// Negotiation
export function startVulnNegotiation(agreementId: string): Promise<{ status: string }> {
  return post<{ status: string }>(`/vulns/negotiations/${agreementId}/start`, {});
}

export function getVulnNegotiationStatus(agreementId: string): Promise<any> {
  return get<any>(`/vulns/negotiations/${agreementId}/status`);
}

export function getVulnOutcome(agreementId: string): Promise<VulnOutcomeResponse> {
  return get<VulnOutcomeResponse>(`/vulns/negotiations/${agreementId}/outcome`);
}
