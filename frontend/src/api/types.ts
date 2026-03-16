// Auth
export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  role: "seller" | "buyer";
  display_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// Inventions
export interface InventionCreateRequest {
  title: string;
  anonymized_summary?: string;
  category?: string;
  full_description: string;
  technical_domain: string;
  novelty_claims: string[];
  prior_art_known?: string[];
  potential_applications?: string[];
  development_stage: string;
  self_assessed_value: number;
  outside_option_value: number;
  confidential_sections?: string[];
  max_disclosure_fraction?: number;
}

export interface InventionResponse {
  id: string;
  title: string;
  anonymized_summary: string | null;
  category: string | null;
  status: string;
}

export interface ListingResponse {
  id: string;
  title: string;
  anonymized_summary: string | null;
  category: string | null;
  development_stage: string;
}

// Agreements
export interface AgreementCreateRequest {
  invention_id: string;
  budget_cap: number;
}

export interface AgreementResponse {
  id: string;
  invention_id: string;
  seller_id: string;
  buyer_id: string;
  status: string;
  alpha_0: number | null;
  budget_cap: number | null;
  theta: number | null;
}

export interface AgreementParamsRequest {
  alpha_0?: number;
  budget_cap?: number;
}

// Negotiations
export interface NegotiationOutcomeResponse {
  outcome: string;
  final_price: number | null;
  reason: string | null;
  negotiation_rounds: number | null;
}

export interface NegotiationStatusResponse {
  status: "pending" | "running" | "completed" | "error";
  outcome?: NegotiationOutcomeResponse;
  error?: string;
}

// SSE events
export interface NegotiationProgressEvent {
  phase: string;
  data?: Record<string, unknown>;
}
