import { get, post, patch, uploadFile } from "./client";

export interface RFPCreateRequest {
  title: string;
  target_software: string;
  target_version_range: string;
  desired_capability: string;
  threat_model?: string;
  target_environment?: Record<string, unknown>;
  acceptance_criteria?: string;
  budget_min_eth: number;
  budget_max_eth: number;
  deadline: string;
  exclusivity_preference?: string;
}

export interface RFPResponse {
  id: string;
  buyer_id: string;
  title: string;
  target_software: string;
  target_version_range: string;
  desired_capability: string;
  threat_model: string | null;
  target_environment: Record<string, unknown> | null;
  acceptance_criteria: string | null;
  has_patches: boolean;
  budget_min_eth: number;
  budget_max_eth: number;
  deadline: string;
  exclusivity_preference: string;
  status: string;
  created_at: string;
}

export interface RFPListingResponse {
  id: string;
  title: string;
  target_software: string;
  target_version_range: string;
  desired_capability: string;
  has_patches: boolean;
  budget_min_eth: number;
  budget_max_eth: number;
  deadline: string;
  exclusivity_preference: string;
  status: string;
}

export interface ProposalCreateRequest {
  vulnerability_id?: string;
  message?: string;
  proposed_price_eth: number;
  estimated_delivery_days?: number;
}

export interface ProposalResponse {
  id: string;
  rfp_id: string;
  seller_id: string;
  vulnerability_id: string | null;
  message: string | null;
  proposed_price_eth: number;
  estimated_delivery_days: number;
  status: string;
  created_at: string;
}

export const createRFP = (data: RFPCreateRequest) => post<RFPResponse>("/rfps/", data);
export const listMyRFPs = () => get<RFPResponse[]>("/rfps/");
export const listRFPListings = () => get<RFPListingResponse[]>("/rfps/listings");
export const getRFP = (id: string) => get<RFPResponse>(`/rfps/${id}`);
export const updateRFP = (id: string, data: Partial<RFPCreateRequest>) => patch<RFPResponse>(`/rfps/${id}`, data);
export const cancelRFP = (id: string) => post<RFPResponse>(`/rfps/${id}/cancel`);
export const uploadPatches = (id: string, file: File) => uploadFile<{ status: string; hash: string }>(`/rfps/${id}/upload-patches`, file);
export const submitProposal = (rfpId: string, data: ProposalCreateRequest) => post<ProposalResponse>(`/rfps/${rfpId}/proposals`, data);
export const listProposals = (rfpId: string) => get<ProposalResponse[]>(`/rfps/${rfpId}/proposals`);
export const acceptProposal = (proposalId: string) => post<ProposalResponse>(`/rfps/proposals/${proposalId}/accept`);
