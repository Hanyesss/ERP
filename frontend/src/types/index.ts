export type UserRole = "employee" | "seller" | "manager" | "purchaser" | "accountant" | "admin" | "partner";
export type UserLang = "ru" | "zh";

export interface User {
  id: string;
  full_name: string;
  roles: UserRole[];
  lang: UserLang;
}

export type PartnerPayoutStatus = "pending" | "approved" | "paid" | "rejected";

export interface PartnerClient {
  id: string;
  name: string;
  name_cn?: string;
  code?: string;
}

export interface PartnerSummary {
  partner_id: string;
  partner_name: string;
  clients: PartnerClient[];
  total_accrued: number;
  total_paid: number;
  balance: number;
  total_weight_kg: number;
}

export interface PartnerOrder {
  id: string;
  order_number: string;
  client_id: string;
  client_name?: string;
  business_type_name?: string;
  order_date: string;
  status: string;
  payment_status: string;
  sale_cny: number;
  cost_cny: number;
  margin_cny: number;
  share_cny: number;
  weight_kg?: number;
  expenses_cny?: number;
}

export interface PartnerPayout {
  id: string;
  partner_counterparty_id: string;
  partner_name?: string;
  period_from?: string;
  period_to?: string;
  amount: number;
  status: PartnerPayoutStatus;
  notes?: string;
  expense_id?: string;
  created_at?: string;
}

export interface AdminPartner {
  partner_id: string;
  partner_name: string;
  total_accrued: number;
  total_paid: number;
  balance: number;
}
