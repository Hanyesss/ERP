import apiClient from "./client";
import type { Order, OrderListResponse, OrderFormData } from "../types/order";

export interface OrderListParams {
  search?: string;
  client_id?: string;
  business_type_id?: string;
  status?: string;
  manager_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export const getOrders = (params: OrderListParams = {}) =>
  apiClient.get<OrderListResponse>("/api/orders", { params });

export const getOrder = (id: string) =>
  apiClient.get<Order>(`/api/orders/${id}`);

export const getNextOrderNumber = (date: string) =>
  apiClient.get<{ order_number: string }>("/api/orders/next-number", { params: { date } });

export const createOrder = (data: OrderFormData) =>
  apiClient.post<Order>("/api/orders", data);

export const updateOrder = (id: string, data: Partial<OrderFormData>) =>
  apiClient.patch<Order>(`/api/orders/${id}`, data);

export const cancelOrder = (id: string) =>
  apiClient.delete(`/api/orders/${id}`);

export const closeOrder = (id: string) =>
  apiClient.post<Order>(`/api/orders/${id}/close`);

export const getOrderHistory = (id: string) =>
  apiClient.get<any[]>(`/api/orders/${id}/history`);
