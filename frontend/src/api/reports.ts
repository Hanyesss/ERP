import apiClient from "./client";

const BASE = "/api/reports";

export interface PnLData {
  date_from: string;
  date_to: string;
  prev_date_from: string;
  prev_date_to: string;
  revenue: number;
  outgoing: number;
  expenses: number;
  net_profit: number;
  expenses_by_category: { category_name: string; category_name_cn: string; amount_cny: number }[];
  prev_period: {
    revenue: number;
    outgoing: number;
    expenses: number;
    net_profit: number;
  };
  pct_revenue: number | null;
  pct_net_profit: number | null;
}

export interface ByClientRow {
  client_id: string;
  client_name: string;
  revenue: number;
  paid_by_client: number;
  paid_to_supplier: number;
  unallocated_cny: number;
  cogs: number;
  direct_expenses: number;
  client_expenses: number;
  net_profit: number;
  balance: number; // positive = overpayment, negative = debt
}

export interface ClientOrderRow {
  order_id: string;
  order_number: string;
  order_date: string;
  total_sale_cny: number;
  cogs: number;
  direct_expenses: number;
  paid_cny: number;
  payment_status: string;
  remaining: number;
  profit: number;
}

export interface ClientDetailData {
  client_id: string;
  client_name: string;
  orders: ClientOrderRow[];
  client_expenses: number;
  total_revenue: number;
  total_cogs: number;
  total_direct_expenses: number;
  total_paid: number;
  unallocated_cny: number;
  total_profit: number;
  balance: number;
}

export interface SupplierPurchaseRow {
  purchase_id: string;
  purchase_number: string;
  purchase_date: string;
  order_number: string | null;
  order_sale_cny: number | null;
  total_amount_cny: number;
  paid_cny: number;
  payment_status: string;
  remaining: number;
}

export interface SupplierDetailData {
  supplier_id: string;
  supplier_name: string;
  purchases: SupplierPurchaseRow[];
  total_purchased_cny: number;
  total_paid_cny: number;
  balance: number;
}

export interface BySupplierRow {
  supplier_id: string;
  supplier_name: string;
  total_purchased_cny: number;
  paid_cny: number;
  debt_cny: number;
  count: number;
  has_overdue: boolean;
}

export interface ExpensesData {
  total: number;
  items: { category_name: string; category_name_cn: string; amount_cny: number; count: number; percent: number }[];
}

export interface TonnageData {
  total_weight_kg: number;
  total_volume_m3: number;
  order_count: number;
  by_warehouse: {
    warehouse_id: string;
    warehouse_name: string;
    warehouse_name_cn: string;
    order_count: number;
    total_weight_kg: number;
    total_volume_m3: number;
  }[];
  by_month: { year: number; month: number; total_weight_kg: number; total_volume_m3: number }[];
}

export const getPnL = (params: {
  date_from: string;
  date_to: string;
  business_type_id?: string;
  warehouse_id?: string;
}) => apiClient.get<PnLData>(`${BASE}/pnl`, { params });

export const getByClient = (params: { date_from: string; date_to: string; business_type_id?: string }) =>
  apiClient.get<ByClientRow[]>(`${BASE}/by-client`, { params });

export const getClientDetail = (
  clientId: string,
  params: { date_from: string; date_to: string }
) => apiClient.get<ClientDetailData>(`${BASE}/by-client/${clientId}`, { params });

export const getBySupplier = (params: { date_from: string; date_to: string }) =>
  apiClient.get<BySupplierRow[]>(`${BASE}/by-supplier`, { params });

export const getSupplierDetail = (
  supplierId: string,
  params: { date_from: string; date_to: string }
) => apiClient.get<SupplierDetailData>(`${BASE}/by-supplier/${supplierId}`, { params });

export const getExpensesReport = (params: {
  date_from: string;
  date_to: string;
  link_type?: string;
}) => apiClient.get<ExpensesData>(`${BASE}/expenses`, { params });

export interface ByDirectionRow {
  direction_id: string;
  direction_name: string;
  direction_name_cn: string;
  revenue: number;
  paid_by_client: number;
  paid_to_supplier: number;
  cogs: number;
  direct_expenses: number;
  net_profit: number;
  balance: number;
}

export const getByDirection = (params: { date_from: string; date_to: string }) =>
  apiClient.get<ByDirectionRow[]>(`${BASE}/by-direction`, { params });

export const getTonnage = (params: {
  date_from: string;
  date_to: string;
  warehouse_id?: string;
  client_id?: string;
}) => apiClient.get<TonnageData>(`${BASE}/tonnage`, { params });

async function downloadExcel(path: string, params: Record<string, any>, filename: string) {
  const response = await apiClient.get(path, {
    params: Object.fromEntries(Object.entries(params).filter(([, v]) => v != null)),
    responseType: "blob",
  });
  const url = URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const exportPnL = (params: { date_from: string; date_to: string; lang: string }) =>
  downloadExcel(`${BASE}/pnl/export`, params, `pnl_${params.date_from}_${params.date_to}.xlsx`);

export const exportByClient = (params: { date_from: string; date_to: string; lang: string; business_type_id?: string }) =>
  downloadExcel(`${BASE}/by-client/export`, params, `by_client_${params.date_from}_${params.date_to}.xlsx`);

export const exportBySupplier = (params: { date_from: string; date_to: string; lang: string }) =>
  downloadExcel(`${BASE}/by-supplier/export`, params, `by_supplier_${params.date_from}_${params.date_to}.xlsx`);

export const exportExpenses = (params: { date_from: string; date_to: string; lang: string }) =>
  downloadExcel(`${BASE}/expenses/export`, params, `expenses_${params.date_from}_${params.date_to}.xlsx`);

export const exportTonnage = (params: { date_from: string; date_to: string; lang: string }) =>
  downloadExcel(`${BASE}/tonnage/export`, params, `tonnage_${params.date_from}_${params.date_to}.xlsx`);

export const exportTonnageDetail = (
  params: { date_from: string; date_to: string; lang: string; warehouse_id?: string; client_id?: string },
  filenameSuffix = "",
) =>
  downloadExcel(
    `${BASE}/tonnage/detail/export`,
    params,
    `tonnage_detail${filenameSuffix}_${params.date_from}_${params.date_to}.xlsx`,
  );
