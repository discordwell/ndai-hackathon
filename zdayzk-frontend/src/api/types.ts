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

// Known Targets
export interface KnownTarget {
  id: string;
  slug: string;
  display_name: string;
  icon_emoji: string;
  platform: "linux" | "windows" | "ios";
  current_version: string;
  escrow_amount_usd: number;
  verification_method: "nitro" | "ec2" | "manual";
  has_prebuilt: boolean;
}

export interface KnownTargetDetail extends KnownTarget {
  description: string;
  poc_instructions: string;
  build_status: string;
  supported_capabilities: string[];
  max_poc_size_kb: number;
}

// Proposals
export interface ProposalCreate {
  target_id: string;
  poc_script: string;
  script_type: "bash" | "python3" | "html" | "powershell";
  claimed_capability: string;
  reliability_runs: number;
  asking_price_eth: number;
}

export interface Proposal {
  id: string;
  target_id: string;
  target_name: string;
  claimed_capability: string;
  status: string;
  created_at: string;
  asking_price_eth: number;
}

export interface ProposalDetail extends Proposal {
  poc_script: string;
  script_type: string;
  reliability_runs: number;
  deposit_tx_hash: string | null;
  deposit_confirmed: boolean;
  verification_result: VerificationResult | null;
  listing_id: string | null;
}

export interface VerificationResult {
  claimed_capability: string;
  verified_capability: string;
  reliability_score: number;
  passed: boolean;
  error: string | null;
}

// Badges
export interface BadgeStatus {
  has_badge: boolean;
  badge_tier: string | null;
  eth_address: string | null;
  purchased_at: string | null;
}
