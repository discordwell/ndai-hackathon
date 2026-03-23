/**
 * ZK auction API client.
 */
import { zkGet, zkPost } from "./zkClient";

// ── Request types ──

export interface ZKAuctionCreateRequest {
  vulnerability_id: string;
  reserve_price_eth: number;
  duration_hours: number;
  serious_customers_only?: boolean;
}

export interface ZKAuctionBidRequest {
  eth_address: string;
  bid_tx_hash: string;
  bid_eth: number;
}

// ── Response types ──

export interface ZKAuctionResponse {
  id: string;
  vulnerability_id: string;
  seller_pubkey: string;
  reserve_price_eth: number;
  duration_hours: number;
  serious_customers_only: boolean;
  status: string;
  highest_bid_eth: number | null;
  highest_bidder_pubkey: string | null;
  end_time: string | null;
  auction_contract_address: string | null;
  created_at: string;
}

export interface ZKAuctionBidResponse {
  id: string;
  auction_id: string;
  bidder_pubkey: string;
  bid_eth: number;
  bid_tx_hash: string | null;
  is_highest: boolean;
  created_at: string;
}

// ── API functions ──

export function listAuctions() {
  return zkGet<ZKAuctionResponse[]>("/zk-auctions/");
}

export function getAuction(id: string) {
  return zkGet<ZKAuctionResponse>(`/zk-auctions/${id}`);
}

export function createAuction(data: ZKAuctionCreateRequest) {
  return zkPost<ZKAuctionResponse>("/zk-auctions/", data);
}

export function placeBid(auctionId: string, data: ZKAuctionBidRequest) {
  return zkPost<ZKAuctionBidResponse>(`/zk-auctions/${auctionId}/bid`, data);
}

export function endAuction(id: string) {
  return zkPost<ZKAuctionResponse>(`/zk-auctions/${id}/end`);
}

export function settleAuction(id: string) {
  return zkPost<ZKAuctionResponse>(`/zk-auctions/${id}/settle`);
}

export function cancelAuction(id: string) {
  return zkPost<ZKAuctionResponse>(`/zk-auctions/${id}/cancel`);
}

export function listBids(auctionId: string) {
  return zkGet<ZKAuctionBidResponse[]>(`/zk-auctions/${auctionId}/bids`);
}
