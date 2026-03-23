import { get, post } from "./client";

export interface SecretPolicy {
  allowed_actions: string[];
  max_uses: number;
}

export interface SecretCreateRequest {
  name: string;
  description?: string;
  secret_value: string;
  policy: SecretPolicy;
}

export interface SecretResponse {
  id: string;
  name: string;
  description: string | null;
  policy: SecretPolicy;
  uses_remaining: number;
  status: string;
  created_at: string;
  is_owner: boolean;
}

export interface SecretUseResponse {
  action: string;
  result: string;
  success: boolean;
  secret_name: string;
  attestation_available: boolean;
  policy_report: any | null;
  policy_constraints: any[] | null;
  egress_log: any[] | null;
  verification: any | null;
}

export interface AccessLogEntry {
  id: number;
  secret_id: string;
  requester_id: string;
  requester_display_name: string | null;
  action_requested: string;
  status: string;
  result_summary: string | null;
  verification_data: any | null;
  created_at: string;
}

export const createSecret = (data: SecretCreateRequest) => post<SecretResponse>("/secrets/", data);
export const listMySecrets = () => get<SecretResponse[]>("/secrets/");
export const listAvailableSecrets = () => get<SecretResponse[]>("/secrets/available");
export const getSecret = (id: string) => get<SecretResponse>(`/secrets/${id}`);
export const useSecret = (id: string, action: string) => post<SecretUseResponse>(`/secrets/${id}/use`, { action });
export const revokeSecret = (id: string) => post<SecretResponse>(`/secrets/${id}/revoke`, {});
export const getAccessLog = (id: string) => get<AccessLogEntry[]>(`/secrets/${id}/access-log`);
