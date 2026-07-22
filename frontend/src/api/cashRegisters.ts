import apiClient from "./client";

export interface CashRegister {
  id: string;
  name: string;
  currency: string;
  notes?: string;
  is_active: boolean;
  balance: number;
  initial_balance: number;
}

export interface CashTransaction {
  id: string;
  payment_id?: string;
  direction: "in" | "out";
  amount: number;
  balance_after: number;
  operation_type?: string;  // системный ключ — переводится через t("cash.op.{key}")
  notes?: string;           // пользовательский текст — показывается как есть
  reason?: string;          // номер заказа / закупки
  is_active: boolean;
  created_by_name: string;
  created_at: string;
}

export const getCashRegisters = () =>
  apiClient.get<CashRegister[]>("/api/cash-registers");

export const createCashRegister = (data: { name: string; currency: string; notes?: string; initial_balance?: number }) =>
  apiClient.post<CashRegister>("/api/cash-registers", data);

export const updateCashRegister = (id: string, data: Partial<{ name: string; currency: string; notes: string; is_active: boolean; initial_balance: number }>) =>
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

export const exportCashMovements = async (params: {
  date_from: string;
  date_to: string;
  register_ids: string[];
  lang: string;
}) => {
  const response = await apiClient.get("/api/cash-registers/export/movements", {
    params,
    responseType: "blob",
    // register_ids как повторяющиеся query-параметры (?register_ids=a&register_ids=b)
    paramsSerializer: { indexes: null },
  });
  const url = URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = `cash_movements_${params.date_from}_${params.date_to}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
};
