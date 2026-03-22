import { get, getBlob } from "./client";
import type { DeliveryStatusResponse } from "./types";

export function getDeliveryStatus(
  agreementId: string
): Promise<DeliveryStatusResponse> {
  return get<DeliveryStatusResponse>(`/delivery/${agreementId}/status`);
}

export function downloadPayload(agreementId: string): Promise<Blob> {
  return getBlob(`/delivery/${agreementId}/payload`);
}

export function downloadKey(agreementId: string): Promise<Blob> {
  return getBlob(`/delivery/${agreementId}/key`);
}
