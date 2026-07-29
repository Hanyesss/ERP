import apiClient from "./client";

export interface PlanInstallment {
  id: string;
  kind?: string | null;          // "deposit" | "balance"
  amount: number;
  currency: string;
  amount_cny: number;
  payment_date: string;
  created_by_name: string;
}

export interface PaymentPlan {
  id: string;
  direction: "in" | "out";
  order_id?: string | null;
  purchase_id?: string | null;
  doc_number?: string | null;
  counterparty_id: string;
  counterparty_name?: string | null;
  currency: string;
  expected_amount: number;
  expected_cny: number;
  paid_cny: number;
  remaining_cny: number;
  status: "pending" | "deposit" | "paid";
  installments: PlanInstallment[];
  created_at?: string | null;
}

export interface PlanListResponse {
  items: PaymentPlan[];
  total: number;
  page: number;
  page_size: number;
}

export const getPaymentPlans = (params?: {
  direction?: string; status?: string; search?: string;
  order_id?: string; purchase_id?: string; page?: number; page_size?: number;
}) => apiClient.get<PlanListResponse>("/api/payment-plans", { params });

export const getPaymentPlan = (id: string) =>
  apiClient.get<PaymentPlan>(`/api/payment-plans/${id}`);
