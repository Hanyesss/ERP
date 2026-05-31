import apiClient from "./client";

export interface CashRegister {
  id: string;
  name: string;
  currency: string;
  notes?: string;
  is_active: boolean;
  balance: number;
}

export interface CashTransaction {
  id: string;
  payment_id?: string;
  direction: "in" | "out";
  amount: number;
  balance_after: number;
  notes?: string;
  created_by_name: string;
  created_at: string;
}

export const getCashRegisters = () =>
  apiClient.get<CashRegister[]>("/api/cash-registers");

export const createCashRegister = (data: { name: string; currency: string; notes?: string }) =>
  apiClient.post<CashRegister>("/api/cash-registers", data);

export const updateCashRegister = (id: string, data: Partial<{ name: string; currency: string; notes: string; is_active: boolean }>) =>
  apiClient.patch<CashRegister>(`/api/cash-registers/${id}`, data);

export const getCashTransactions = (id: string, params?: { page?: number; page_size?: number }) =>
  apiClient.get<CashTransaction[]>(`/api/cash-registers/${id}/transactions`, { params });
