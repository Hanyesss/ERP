export type PaymentDirection = "in" | "out";
export type PaymentCurrency = "CNY" | "RUB" | "USDT" | "USD";

export interface PaymentAllocation {
  id: string;
  order_id?: string;
  order_number?: string;
  purchase_id?: string;
  purchase_number?: string;
  amount_cny: number;
  notes?: string;
}

export interface Payment {
  id: string;
  direction: PaymentDirection;
  counterparty_id: string;
  counterparty_name: string;
  payment_date: string;
  currency: PaymentCurrency;
  amount: number;
  rate_to_cny: number;
  amount_cny: number;
  network_fee?: number;
  notes?: string;
  file_url?: string;
  file_urls: string[];
  pending_change?: string;
  is_active: boolean;
  created_by_name: string;
  created_at: string;
  allocations: PaymentAllocation[];
  allocated_cny: number;
  unallocated_cny: number;
}

export interface PaymentListItem {
  id: string;
  direction: PaymentDirection;
  counterparty_id: string;
  counterparty_name: string;
  payment_date: string;
  currency: PaymentCurrency;
  amount: number;
  amount_cny: number;
  rate_to_cny: number;
  allocations_count: number;
  allocated_cny: number;
  is_active: boolean;
  created_by_name: string;
}

export interface PaymentListResponse {
  items: PaymentListItem[];
  total: number;
  page: number;
  page_size: number;
  total_incoming_cny: number;
  total_outgoing_cny: number;
}

export interface AllocationInput {
  order_id?: string;
  purchase_id?: string;
  amount_cny: number;
  notes?: string;
}

export interface PaymentCreateInput {
  direction: PaymentDirection;
  counterparty_id: string;
  cash_register_id: string;
  payment_date: string;
  currency: PaymentCurrency;
  amount: number;
  rate_to_cny: number;
  network_fee?: number;
  notes?: string;
  allocations: AllocationInput[];
  cash_rate?: number;
  plan_id?: string;
  installment_kind?: string;
}

export interface OrderPaymentBalance {
  order_id: string;
  order_number: string;
  total_cny: number;
  paid_cny: number;
  remaining_cny: number;
  payment_status: string;
}

export interface PurchasePaymentBalance {
  purchase_id: string;
  purchase_number: string;
  total_cny: number;
  paid_cny: number;
  remaining_cny: number;
  payment_status: string;
}
