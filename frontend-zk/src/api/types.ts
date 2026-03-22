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
