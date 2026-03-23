/**
 * Serious Customer API client.
 */
import { zkGet, zkPost } from "./zkClient";

export interface SeriousCustomerStatusResponse {
  is_serious_customer: boolean;
  sc_type: string | null;
  sc_deposit_eth: number | null;
  sc_eth_address: string | null;
  sc_awarded_at: string | null;
  sc_refunded: boolean;
  min_deposit_eth: number | null;
}

export interface MinDepositResponse {
  min_deposit_eth: number;
  eth_price_usd: number;
}

export interface SeriousCustomerDepositRequest {
  eth_address: string;
  tx_hash: string;
  deposit_eth: number;
}

export function getSCStatus() {
  return zkGet<SeriousCustomerStatusResponse>("/serious-customer/status");
}

export function registerSCDeposit(data: SeriousCustomerDepositRequest) {
  return zkPost<SeriousCustomerStatusResponse>("/serious-customer/deposit", data);
}

export function getMinDeposit() {
  return zkGet<MinDepositResponse>("/serious-customer/min-deposit");
}
