import { get } from "./client";
import type { KnownTarget, KnownTargetDetail } from "./types";

export function getTargets(): Promise<KnownTarget[]> {
  return get<KnownTarget[]>("/targets/");
}

export function getTarget(id: string): Promise<KnownTargetDetail> {
  return get<KnownTargetDetail>(`/targets/${id}`);
}
