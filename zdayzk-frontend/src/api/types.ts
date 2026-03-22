// Auth
export interface RegisterRequest {
  email: string;
  password: string;
  display_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export interface UserProfile {
  id: string;
  email: string;
  role: string;
  display_name: string | null;
}

// Vulns
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

// Delivery
export interface DeliveryStatusResponse {
  delivery_hash: string;
  key_commitment: string;
  status: string;
}
