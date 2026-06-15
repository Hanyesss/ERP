import apiClient from "./client";
import type {
  Expense, ExpenseListResponse, ExpenseCreateInput, ReimbursementBalance,
} from "../types/expense";

export interface ExpenseListParams {
  date_from?: string;
  date_to?: string;
  category_id?: string;
  link_type?: string;
  order_id?: string;
  client_id?: string;
  currency?: string;
  is_reimbursement?: boolean;
  reimburse_status?: string;
  created_by_id?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export const getExpenses = (params: ExpenseListParams = {}) =>
  apiClient.get<ExpenseListResponse>("/api/expenses", { params });

export const getExpense = (id: string) =>
  apiClient.get<Expense>(`/api/expenses/${id}`);

export const createExpense = (data: ExpenseCreateInput) =>
  apiClient.post<Expense>("/api/expenses", data);

export const updateExpense = (id: string, data: Partial<ExpenseCreateInput>) =>
  apiClient.patch<Expense>(`/api/expenses/${id}`, data);

export const deleteExpense = ({ id, reason }: { id: string; reason: string }) =>
  apiClient.delete(`/api/expenses/${id}`, { data: { reason } });

export const approveReimbursement = (id: string, amount?: number) =>
  apiClient.post(`/api/expenses/${id}/approve`, amount !== undefined ? { amount } : {});

export const rejectReimbursement = (id: string, reject_reason: string) =>
  apiClient.post(`/api/expenses/${id}/reject`, { reject_reason });

export const markReimbursementPaid = (
  id: string,
  data: { paid_date: string; cash_register_id?: string }
) => apiClient.post(`/api/expenses/${id}/mark-paid`, data);

export const getMyBalance = () =>
  apiClient.get<ReimbursementBalance>("/api/expenses/my-balance");

export const getUserBalance = (userId: string) =>
  apiClient.get<ReimbursementBalance>(`/api/expenses/user/${userId}/balance`);

export const uploadReceipt = (id: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient.post<import("../types/expense").Expense>(`/api/expenses/${id}/receipt`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const uploadQrPhoto = (id: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient.post<import("../types/expense").Expense>(`/api/expenses/${id}/qr`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const deleteQrPhoto = (id: string) =>
  apiClient.delete(`/api/expenses/${id}/qr`);

export const getExpenseHistory = (id: string) =>
  apiClient.get<any[]>(`/api/expenses/${id}/history`);

export const requestExpenseChange = (id: string, data: { amount?: number; currency?: string; rate_to_cny?: number; reason?: string }) =>
  apiClient.post(`/api/expenses/${id}/request-change`, data);

export const approveExpenseChange = (id: string) =>
  apiClient.post<import("../types/expense").Expense>(`/api/expenses/${id}/approve-change`);

export const rejectExpenseChange = (id: string) =>
  apiClient.post<import("../types/expense").Expense>(`/api/expenses/${id}/reject-change`);

export const getFileUrl = (filePath: string) =>
  `${apiClient.defaults.baseURL}/files/${filePath}`;
