import apiClient from "./client";
import type { Purchase, PurchaseListResponse, PurchaseFormData } from "../types/purchase";
import type { AvailableForPurchaseItem } from "../types/order";

export interface PurchaseListParams {
  search?: string;
  supplier_id?: string;
  payment_status?: string;
  date_from?: string;
  date_to?: string;
  order_id?: string;
  business_type_id?: string;
  page?: number;
  page_size?: number;
}

export const getPurchases = (params: PurchaseListParams = {}) =>
  apiClient.get<PurchaseListResponse>("/api/purchases", { params });

export const getPurchase = (id: string) =>
  apiClient.get<Purchase>(`/api/purchases/${id}`);

export const getNextPurchaseNumber = (date: string) =>
  apiClient.get<{ purchase_number: string }>("/api/purchases/next-number", { params: { date } });

export const createPurchase = (data: PurchaseFormData) =>
  apiClient.post<Purchase>("/api/purchases", data);

export const updatePurchase = (id: string, data: Partial<PurchaseFormData>) =>
  apiClient.patch<Purchase>(`/api/purchases/${id}`, data);

export const deletePurchase = (id: string) =>
  apiClient.delete(`/api/purchases/${id}`);

export const getAvailableForPurchase = (orderId: string) =>
  apiClient.get<AvailableForPurchaseItem[]>(`/api/orders/${orderId}/available-for-purchase`);

export interface StockItem {
  id: string;
  name: string;
  name_cn?: string;
  unit?: string;
  quantity: number;
  remaining_quantity: number;
  cost_price: number;
  cost_price_cny: number;
  currency: string;
  purchase_id: string;
  purchase_number: string;
  purchase_date: string;
}

export const getStockItems = (params: { search?: string; only_available?: boolean } = {}) =>
  apiClient.get<StockItem[]>("/api/purchases/stock-items", { params });

export const requestPayment = (id: string) =>
  apiClient.post<Purchase>(`/api/purchases/${id}/request-payment`);
