import { get, post } from "./client";
import type {
  PokerTableSummary,
  CreateTableRequest,
  JoinTableRequest,
  PlayerActionRequest,
  TableView,
} from "./pokerTypes";

export const listTables = () => get<PokerTableSummary[]>("/poker/tables");
export const createTable = (data: CreateTableRequest) => post<PokerTableSummary>("/poker/tables", data);
export const getTableState = (id: string) => get<TableView>(`/poker/tables/${id}`);
export const joinTable = (id: string, data: JoinTableRequest) => post<any>(`/poker/tables/${id}/join`, data);
export const leaveTable = (id: string) => post<any>(`/poker/tables/${id}/leave`, {});
export const submitAction = (tableId: string, data: PlayerActionRequest) => post<any>(`/poker/tables/${tableId}/action`, data);
export const startHand = (tableId: string) => post<any>(`/poker/tables/${tableId}/start-hand`, {});
