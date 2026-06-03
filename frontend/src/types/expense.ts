export type LinkType = "order" | "client" | "none";
export type ReimburseStatus = "pending" | "approved" | "paid" | "rejected";

export interface ExpenseCategory {
  id: string;
  name: string;
  name_cn?: string;
}

export interface ExpenseListItem {
  id: string;
  expense_date: string;
  category_id: string;
  category_name: string;
  category_name_cn?: string;
  currency: string;
  amount: number;
  amount_cny: number;
  link_type: LinkType;
  order_id?: string;
  order_number?: string;
  client_id?: string;
  client_name?: string;
  is_reimbursement: boolean;
  reimburse_to_user_id?: string;
  reimburse_to_name?: string;
  reimburse_status?: ReimburseStatus;
  description: string;
  receipt_url?: string;
  cash_register_id?: string;
  cash_register_name?: string;
  created_by: string;
  created_by_name: string;
  created_at: string;
  is_active: boolean;
}

export interface Expense extends ExpenseListItem {
  rate_to_cny: number;
  reimburse_paid_date?: string;
  reject_reason?: string;
  cash_register_id?: string;
  cash_register_name?: string;
}

export interface ExpenseListResponse {
  items: ExpenseListItem[];
  total: number;
  page: number;
  page_size: number;
  total_cny: number;
  total_order_cny: number;
  total_client_cny: number;
  total_none_cny: number;
}

export interface ExpenseCreateInput {
  expense_date: string;
  category_id: string;
  currency: string;
  amount: number;
  rate_to_cny?: number;
  link_type: LinkType;
  order_id?: string;
  client_id?: string;
  description: string;
  receipt_url?: string;
  is_reimbursement: boolean;
  reimburse_to_user_id?: string;
}

export interface ReimbursementBalance {
  approved_amount_cny: number;
  paid_amount_cny: number;
  owed_cny: number;
  pending_count: number;
  approved_count: number;
}
