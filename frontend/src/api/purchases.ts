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

export const requestPayment = (id: string) =>
  apiClient.post<Purchase>(`/api/purchases/${id}/request-payment`);
