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

export interface VulnAgreementResponse {
  id: string;
  vulnerability_id: string;
  seller_id: string;
  buyer_id: string;
  status: string;
  alpha_0: number | null;
  budget_cap: number | null;
}

export const createVuln = (data: VulnCreateRequest) => post<VulnResponse>("/zk-vulns/", data);
export const listVulns = () => get<VulnResponse[]>("/zk-vulns/");
export const listVulnListings = () => get<VulnListingResponse[]>("/zk-vulns/listings");
export const getVuln = (id: string) => get<VulnResponse>(`/zk-vulns/${id}`);
export const createVulnAgreement = (vulnId: string, budgetCap: number) =>
  post<VulnAgreementResponse>(`/zk-vulns/agreements`, { vulnerability_id: vulnId, budget_cap: budgetCap });
export const listVulnAgreements = () => get<VulnAgreementResponse[]>("/zk-vulns/agreements");
export const getVulnAgreement = (id: string) => get<VulnAgreementResponse>(`/zk-vulns/agreements/${id}`);
export const startNegotiation = (id: string) => post<{ status: string }>(`/zk-vulns/negotiations/${id}/start`, {});
