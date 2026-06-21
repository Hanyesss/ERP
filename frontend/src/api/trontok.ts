import apiClient from "./client";

export interface TronTokSettings {
  base_url?: string;
  api_token_masked?: string;
  is_enabled: boolean;
}

export interface TronTokSettingsUpdate {
  api_token?: string;
  base_url?: string;
  is_enabled?: boolean;
}

export interface TronTokBalance {
  available: string;
  frozen?: string;
  total?: string;
}

export const getTronTokSettings = () =>
  apiClient.get<TronTokSettings>("/api/trontok/erp-settings");

export const updateTronTokSettings = (data: TronTokSettingsUpdate) =>
  apiClient.put<TronTokSettings>("/api/trontok/erp-settings", data);

export const testTronTokConnection = (data: { api_token?: string; base_url?: string }) =>
  apiClient.post<{ ok: boolean; message?: string }>("/api/trontok/erp-test", data);

export const getCounterpartyTronTokBalance = (counterpartyId: string) =>
  apiClient.get<{ trontok_linked: boolean; balance: TronTokBalance | null }>(
    `/api/trontok/erp-balance?counterparty_id=${counterpartyId}`
  );
