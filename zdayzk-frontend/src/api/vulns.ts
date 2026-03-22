import { get, post } from "./client";
import type {
  VulnCreateRequest,
  VulnResponse,
  VulnListingResponse,
  VulnAgreementCreateRequest,
  VulnAgreementResponse,
  VulnOutcomeResponse,
} from "./types";

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
export function createVulnAgreement(
  data: VulnAgreementCreateRequest
): Promise<VulnAgreementResponse> {
  return post<VulnAgreementResponse>("/vulns/agreements", data);
}

export function listVulnAgreements(): Promise<VulnAgreementResponse[]> {
  return get<VulnAgreementResponse[]>("/vulns/agreements");
}

export function getVulnAgreement(
  id: string
): Promise<VulnAgreementResponse> {
  return get<VulnAgreementResponse>(`/vulns/agreements/${id}`);
}

// Negotiation
export function startVulnNegotiation(
  agreementId: string
): Promise<{ status: string }> {
  return post<{ status: string }>(
    `/vulns/negotiations/${agreementId}/start`,
    {}
  );
}

export function getVulnNegotiationStatus(
  agreementId: string
): Promise<any> {
  return get<any>(`/vulns/negotiations/${agreementId}/status`);
}

export function getVulnOutcome(
  agreementId: string
): Promise<VulnOutcomeResponse> {
  return get<VulnOutcomeResponse>(
    `/vulns/negotiations/${agreementId}/outcome`
  );
}
