/**
 * Messaging API client.
 */
import { get, post } from "./client";

// ─── Prekeys ───────────────────────────────────────────────────────────

export interface PrekeyBundleUpload {
  identity_x25519_pub: string;
  signed_prekey_pub: string;
  signed_prekey_sig: string;
  signed_prekey_id: number;
  one_time_prekeys: { pub: string; index: number }[];
}

export interface PrekeyBundleResponse {
  identity_pubkey: string;
  identity_x25519_pub: string;
  signed_prekey_pub: string;
  signed_prekey_sig: string;
  signed_prekey_id: number;
  one_time_prekey: { pub: string; index: number } | null;
}

export interface PrekeyStatus {
  remaining_otpks: number;
  signed_prekey_age_hours: number;
}

export function uploadPrekeys(bundle: PrekeyBundleUpload) {
  return post("/messaging/prekeys", bundle);
}

export function fetchPeerPrekeys(pubkey: string): Promise<PrekeyBundleResponse> {
  return get<PrekeyBundleResponse>(`/messaging/prekeys/${pubkey}`);
}

export function getPrekeyStatus(): Promise<PrekeyStatus> {
  return get<PrekeyStatus>("/messaging/prekeys/status");
}

// ─── Conversations ─────────────────────────────────────────────────────

export interface ConversationResponse {
  id: string;
  type: string;
  agreement_id: string | null;
  participant_a: string;
  participant_b: string;
  created_at: string;
  last_message_at: string | null;
  unread_count: number;
}

export function createConversation(body: { peer_pubkey?: string; agreement_id?: string }): Promise<ConversationResponse> {
  return post<ConversationResponse>("/messaging/conversations", body);
}

export function listConversations(): Promise<ConversationResponse[]> {
  return get<ConversationResponse[]>("/messaging/conversations");
}

// ─── Messages ──────────────────────────────────────────────────────────

export interface MessageResponse {
  id: string;
  conversation_id: string;
  sender_pubkey: string;
  ciphertext: string;
  header: string;
  x3dh_header: string | null;
  message_index: number;
  created_at: string;
}

export function getMessages(conversationId: string, before?: string, limit = 50): Promise<MessageResponse[]> {
  let url = `/messaging/conversations/${conversationId}/messages?limit=${limit}`;
  if (before) url += `&before=${encodeURIComponent(before)}`;
  return get<MessageResponse[]>(url);
}

export function sendMessage(conversationId: string, body: {
  ciphertext: string;
  header: string;
  x3dh_header?: string | null;
}): Promise<MessageResponse> {
  return post<MessageResponse>(`/messaging/conversations/${conversationId}/messages`, body);
}
