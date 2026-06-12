import apiClient from "./client";
import type {
  Payment, PaymentListResponse, PaymentCreateInput,
  AllocationInput, OrderPaymentBalance, PurchasePaymentBalance,
} from "../types/payment";

export interface PaymentListParams {
  direction?: string;
  counterparty_id?: string;
  currency?: string;
  has_allocations?: boolean;
  date_from?: string;
  date_to?: string;
  search?: string;
  created_by_id?: string;
  page?: number;
  page_size?: number;
}

export const getPayments = (params: PaymentListParams = {}) =>
  apiClient.get<PaymentListResponse>("/api/payments", { params });

export const getPayment = (id: string) =>
  apiClient.get<Payment>(`/api/payments/${id}`);

export const createPayment = (data: PaymentCreateInput) =>
  apiClient.post<Payment>("/api/payments", data);

export const updatePayment = (id: string, data: Partial<PaymentCreateInput>) =>
  apiClient.patch<Payment>(`/api/payments/${id}`, data);

export const deletePayment = ({ id, reason }: { id: string; reason: string }) =>
  apiClient.delete(`/api/payments/${id}`, { data: { reason } });

export const addAllocations = (id: string, allocations: AllocationInput[]) =>
  apiClient.post<Payment>(`/api/payments/${id}/allocate`, allocations);

export const getOrderPaymentBalance = (orderId: string) =>
  apiClient.get<OrderPaymentBalance>(`/api/payments/balance/order/${orderId}`);

export const getPurchasePaymentBalance = (purchaseId: string) =>
  apiClient.get<PurchasePaymentBalance>(`/api/payments/balance/purchase/${purchaseId}`);

export const getPaymentsForOrder = (orderId: string) =>
  apiClient.get<any[]>(`/api/payments/for-order/${orderId}`);

export const getPaymentsForPurchase = (purchaseId: string) =>
  apiClient.get<any[]>(`/api/payments/for-purchase/${purchaseId}`);

export const uploadPaymentReceipt = (id: string, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return apiClient.post<Payment>(`/api/payments/${id}/receipt`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const deletePaymentReceipt = (id: string) =>
  apiClient.delete(`/api/payments/${id}/receipt`);

export interface DashboardBalances {
  total_receivable_cny: string;
  total_payable_cny: string;
  unpaid_orders_count: number;
  unpaid_purchases_count: number;
}

export const getDashboardBalances = () =>
  apiClient.get<DashboardBalances>("/api/dashboard/balances");
