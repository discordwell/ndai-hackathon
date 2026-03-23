import { get, post } from "./client";

export interface TranscriptSubmitRequest {
  title: string;
  team_name?: string;
  content: string;
}

export interface TranscriptResponse {
  id: string;
  title: string;
  team_name: string | null;
  status: string;
  content_hash: string;
  created_at: string;
}

export interface PaginatedTranscriptResponse {
  items: TranscriptResponse[];
  total: number;
  offset: number;
  limit: number;
}

export interface TranscriptSummaryResponse {
  id: string;
  transcript_id: string;
  executive_summary: string;
  action_items: string[];
  key_decisions: string[];
  dependencies: string[];
  blockers: string[];
  sentiment: string | null;
  attestation_available: boolean;
  created_at: string;
  policy_report: any | null;
  policy_constraints: any[] | null;
  egress_log: any[] | null;
  verification: any | null;
}

export interface AggregationResponse {
  cross_team_summary: string;
  shared_dependencies: string[];
  shared_blockers: string[];
  recommendations: string[];
  transcript_count: number;
  attestation_available: boolean;
  verification: any | null;
}

export const submitTranscript = (data: TranscriptSubmitRequest) => post<TranscriptResponse>("/transcripts/", data);
export const listTranscripts = (offset = 0, limit = 25) => get<PaginatedTranscriptResponse>(`/transcripts/?offset=${offset}&limit=${limit}`);
export const getTranscript = (id: string) => get<TranscriptResponse>(`/transcripts/${id}`);
export const getSummary = (id: string) => get<TranscriptSummaryResponse>(`/transcripts/${id}/summary`);
export const aggregate = (ids: string[]) => post<AggregationResponse>("/transcripts/aggregate", { transcript_ids: ids });
