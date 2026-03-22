/**
 * Bounty API client — buyer-initiated 0day requests.
 */
import { zkGet, zkPost, zkDelete } from "./zkClient";

// ── Request types ──

export interface BountyCreateRequest {
  target_software: string;
  target_version_constraint?: string;
  desired_impact: string;
  desired_vulnerability_class?: string;
  budget_eth: number;
  description: string;
  deadline?: string;
}

export interface BountyRespondRequest {
  target_software: string;
  target_version: string;
  vulnerability_class: string;
  impact_type: string;
  affected_component?: string;
  anonymized_summary?: string;
  cvss_self_assessed: number;
  asking_price_eth: number;
  discovery_date: string;
}

// ── Response types ──

export interface BountyResponse {
  id: string;
  requester_pubkey: string;
  target_software: string;
  target_version_constraint?: string;
  desired_impact: string;
  desired_vulnerability_class?: string;
  budget_eth: number;
  description: string;
  deadline?: string;
  status: string;
  created_at: string;
}

// ── API functions ──

export function createBounty(data: BountyCreateRequest) {
  return zkPost<BountyResponse>("/bounties/", data);
}

export function listOpenBounties() {
  return zkGet<BountyResponse[]>("/bounties/");
}

export function listMyBounties() {
  return zkGet<BountyResponse[]>("/bounties/mine");
}

export function getBounty(id: string) {
  return zkGet<BountyResponse>(`/bounties/${id}`);
}

export function respondToBounty(bountyId: string, data: BountyRespondRequest) {
  return zkPost<{ agreement_id: string }>(`/bounties/${bountyId}/respond`, data);
}

export function cancelBounty(bountyId: string) {
  return zkDelete(`/bounties/${bountyId}`);
}
