import apiClient from "./client";

export interface IntegrationSettings {
  id: string;
  integration_name: string;
  base_url?: string;
  api_token_masked?: string;
  is_enabled: boolean;
  last_sync_at?: string;
  last_sync_status?: string;
  last_sync_error?: string;
  created_at: string;
  updated_at: string;
}

export interface IntegrationSettingsUpdate {
  base_url?: string;
  api_token?: string;
  is_enabled?: boolean;
}

export const getIntegrationSettings = () =>
  apiClient.get<IntegrationSettings>("/api/integration-settings");

export const updateIntegrationSettings = (data: IntegrationSettingsUpdate) =>
  apiClient.put<IntegrationSettings>("/api/integration-settings", data);

export const testIntegrationConnection = (data: { base_url?: string; api_token?: string }) =>
  apiClient.post<{ ok: boolean; message?: string }>("/api/integration-settings/test", data);

export const syncOrderToSite = (orderId: string) =>
  apiClient.post<any>(`/api/orders/${orderId}/sync-to-site`);

export const pushOrderStatus = (orderId: string, status: string, comment?: string) =>
  apiClient.post<any>(`/api/orders/${orderId}/push-status`, { status, comment });

export const bulkSyncToSite = () =>
  apiClient.post<{
    trade_orders: number; trade_errors: number;
    boxes: number; box_errors: number;
    reconciliations: number; recon_errors: number;
  }>("/api/integration-settings/bulk-sync");
