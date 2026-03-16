import { get, post } from "./client";
import type {
  AgreementCreateRequest,
  AgreementParamsRequest,
  AgreementResponse,
} from "./types";

export function createAgreement(
  data: AgreementCreateRequest
): Promise<AgreementResponse> {
  return post<AgreementResponse>("/agreements/", data);
}

export function listAgreements(): Promise<AgreementResponse[]> {
  return get<AgreementResponse[]>("/agreements/");
}

export function getAgreement(id: string): Promise<AgreementResponse> {
  return get<AgreementResponse>(`/agreements/${id}`);
}

export function setAgreementParams(
  id: string,
  data: AgreementParamsRequest
): Promise<AgreementResponse> {
  return post<AgreementResponse>(`/agreements/${id}/params`, data);
}

export function confirmAgreement(id: string): Promise<AgreementResponse> {
  return post<AgreementResponse>(`/agreements/${id}/confirm`);
}
