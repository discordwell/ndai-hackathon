import { get, post } from "./client";
import type {
  NegotiationOutcomeResponse,
  NegotiationStatusResponse,
} from "./types";

export function startNegotiation(
  agreementId: string
): Promise<NegotiationStatusResponse> {
  return post<NegotiationStatusResponse>(
    `/negotiations/${agreementId}/start`
  );
}

export function getNegotiationStatus(
  agreementId: string
): Promise<NegotiationStatusResponse> {
  return get<NegotiationStatusResponse>(
    `/negotiations/${agreementId}/status`
  );
}

export function getNegotiationOutcome(
  agreementId: string
): Promise<NegotiationOutcomeResponse> {
  return get<NegotiationOutcomeResponse>(
    `/negotiations/${agreementId}/outcome`
  );
}
