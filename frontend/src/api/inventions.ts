import { get, post, put, del } from "./client";
import type {
  InventionCreateRequest,
  InventionResponse,
  ListingResponse,
} from "./types";

export function createInvention(
  data: InventionCreateRequest
): Promise<InventionResponse> {
  return post<InventionResponse>("/inventions/", data);
}

export function listInventions(): Promise<InventionResponse[]> {
  return get<InventionResponse[]>("/inventions/");
}

export function getInvention(id: string): Promise<InventionResponse> {
  return get<InventionResponse>(`/inventions/${id}`);
}

export function updateInvention(
  id: string,
  data: Partial<InventionCreateRequest>
): Promise<InventionResponse> {
  return put<InventionResponse>(`/inventions/${id}`, data);
}

export function deleteInvention(id: string): Promise<{ status: string }> {
  return del<{ status: string }>(`/inventions/${id}`);
}

export function listPublicListings(): Promise<ListingResponse[]> {
  return get<ListingResponse[]>("/inventions/listings");
}
