import { get, post } from "./client";
import type {
  ProposalCreate,
  Proposal,
  ProposalDetail,
  BadgeStatus,
} from "./types";

export function createProposal(data: ProposalCreate): Promise<Proposal> {
  return post<Proposal>("/proposals/", data);
}

export function getMyProposals(): Promise<Proposal[]> {
  return get<Proposal[]>("/proposals/");
}

export function getProposal(id: string): Promise<ProposalDetail> {
  return get<ProposalDetail>(`/proposals/${id}`);
}

export function confirmDeposit(
  id: string,
  txHash: string
): Promise<Proposal> {
  return post<Proposal>(`/proposals/${id}/confirm-deposit`, {
    tx_hash: txHash,
  });
}

export function triggerVerification(id: string): Promise<any> {
  return post<any>(`/proposals/${id}/verify`, {});
}

export function getBadgeStatus(): Promise<BadgeStatus> {
  return get<BadgeStatus>("/badges/me");
}

export function purchaseBadge(
  txHash: string,
  ethAddress: string
): Promise<BadgeStatus> {
  return post<BadgeStatus>("/badges/purchase", {
    tx_hash: txHash,
    eth_address: ethAddress,
  });
}
