import { get, post } from "./client";
import type {
  PokerTableSummary,
  CreateTableRequest,
  JoinTableRequest,
  PlayerActionRequest,
  TableView,
  HandSummary,
  HandDetail,
} from "./pokerTypes";

export const listTables = () => get<PokerTableSummary[]>("/poker/tables");
export const createTable = (data: CreateTableRequest) => post<PokerTableSummary>("/poker/tables", data);
export const getTableState = (id: string) => get<TableView>(`/poker/tables/${id}`);
export const joinTable = (id: string, data: JoinTableRequest) => post<any>(`/poker/tables/${id}/join`, data);
export const leaveTable = (id: string) => post<any>(`/poker/tables/${id}/leave`, {});
export const submitAction = (tableId: string, data: PlayerActionRequest) => post<any>(`/poker/tables/${tableId}/action`, data);
export const startHand = (tableId: string) => post<any>(`/poker/tables/${tableId}/start-hand`, {});
export const listHands = (tableId: string, params?: { limit?: number; before?: number }) => {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.before) qs.set("before", String(params.before));
  const suffix = qs.toString() ? `?${qs}` : "";
  return get<HandSummary[]>(`/poker/tables/${tableId}/hands${suffix}`);
};
export const getHandDetail = (tableId: string, handNumber: number) =>
  get<HandDetail>(`/poker/tables/${tableId}/hands/${handNumber}`);
