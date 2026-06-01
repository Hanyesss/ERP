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

export interface CashTransfer {
  id: string;
  from_register_id: string;
  from_register_name: string;
  from_currency: string;
  to_register_id: string;
  to_register_name: string;
  to_currency: string;
  from_amount: number;
  to_amount: number;
  exchange_rate: number;
  transfer_date: string;
  notes?: string;
  created_by_name: string;
  created_at: string;
}

export const createTransfer = (data: {
  from_register_id: string;
  to_register_id: string;
  from_amount: number;
  to_amount: number;
  exchange_rate: number;
  transfer_date: string;
  notes?: string;
}) => apiClient.post<CashTransfer>("/api/cash-registers/transfer", data);

export const getTransfers = (params?: { register_id?: string; page?: number }) =>
  apiClient.get<CashTransfer[]>("/api/cash-registers/transfers", { params });
