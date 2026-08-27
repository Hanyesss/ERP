import apiClient from "./client";
import type { Order, OrderListResponse, OrderFormData, OrderFile, NetStatusEvent } from "../types/order";

export interface OrderListParams {
  search?: string;
  client_id?: string;
  business_type_id?: string;
  status?: string;
  manager_id?: string;
  date_from?: string;
  date_to?: string;
  sync_status?: string;
  source?: string;
  page?: number;
  page_size?: number;
}

export const getOrders = (params: OrderListParams = {}) =>
  apiClient.get<OrderListResponse>("/api/orders", { params });

export const getOrder = (id: string) =>
  apiClient.get<Order>(`/api/orders/${id}`);

export const getNextOrderNumber = (
  date: string,
  opts?: { business_type_code?: string; client_code?: string; places_count?: number }
) =>
  apiClient.get<{ order_number: string }>("/api/orders/next-number", {
    params: { date, ...opts },
  });

export const createOrder = (data: OrderFormData) =>
  apiClient.post<Order>("/api/orders", data);

export const updateOrder = (id: string, data: Partial<OrderFormData>) =>
  apiClient.patch<Order>(`/api/orders/${id}`, data);

export const cancelOrder = ({ id, reason }: { id: string; reason: string }) =>
  apiClient.delete(`/api/orders/${id}`, { data: { reason } });

export const closeOrder = (id: string) =>
  apiClient.post<Order>(`/api/orders/${id}/close`);

export const getOrderHistory = (id: string) =>
  apiClient.get<any[]>(`/api/orders/${id}/history`);

export const getNetEvents = (id: string) =>
  apiClient.get<NetStatusEvent[]>(`/api/orders/${id}/net-events`);

// Files
export const getOrderFiles = (orderId: string) =>
  apiClient.get<OrderFile[]>(`/api/orders/${orderId}/files`);

export const uploadOrderFile = (orderId: string, file: File, fileType: string) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("file_type", fileType);
  return apiClient.post<OrderFile>(`/api/orders/${orderId}/files`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const deleteOrderFile = (orderId: string, fileId: string) =>
  apiClient.delete(`/api/orders/${orderId}/files/${fileId}`);

export const getFileUrl = (filePath: string) =>
  `${apiClient.defaults.baseURL}/files/${filePath}`;

// Order item photos
export const getItemPhotos = (itemId: string) =>
  apiClient.get<any[]>(`/api/order-items/${itemId}/photos`);

export const uploadItemPhoto = (itemId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.post<any>(`/api/order-items/${itemId}/photos`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const deleteItemPhoto = (itemId: string, photoId: string) =>
  apiClient.delete(`/api/order-items/${itemId}/photos/${photoId}`);

export const getItemPhotoUrl = (itemId: string, photoId: string) =>
  `${apiClient.defaults.baseURL}/api/order-items/${itemId}/photos/${photoId}/file`;

export const downloadClientPdf = (orderId: string) =>
  apiClient.get(`/api/orders/${orderId}/client-pdf`, { responseType: "blob" });

export const downloadLogisticsPdf = (orderId: string) =>
  apiClient.get(`/api/orders/${orderId}/logistics-pdf`, { responseType: "blob" });
