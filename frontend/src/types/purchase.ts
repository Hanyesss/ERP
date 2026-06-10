export type PurchasePaymentStatus = "unpaid" | "partial" | "paid";

export interface PurchaseItem {
  id: string;
  order_item_id: string;
  order_item_name?: string;
  order_number?: string;
  quantity: number;
  cost_price: number;
  cost_amount: number;
}

export interface Purchase {
  id: string;
  purchase_number: string;
  supplier_id: string;
  supplier_name: string;
  purchase_date: string;
  currency: string;
  total_amount: number;
  rate_to_cny: number;
  total_amount_cny: number;
  payment_status: PurchasePaymentStatus;
  paid_amount_cny: number;
  remaining_amount_cny: number;
  notes?: string;
  created_at: string;
  items: PurchaseItem[];
  order_id?: string;
  order_number?: string;
  excluded_from_accounting?: boolean;
  payment_requested?: boolean;
  payment_requested_by_name?: string;
  payment_requested_at?: string;
}

export interface PurchaseListItem {
  id: string;
  purchase_number: string;
  supplier_id: string;
  supplier_name: string;
  purchase_date: string;
  currency: string;
  total_amount: number;
  total_amount_cny: number;
  payment_status: PurchasePaymentStatus;
  items_count: number;
  paid_amount_cny: number;
  remaining_amount_cny: number;
  order_id?: string;
  order_number?: string;
  excluded_from_accounting?: boolean;
  payment_requested?: boolean;
}

export interface PurchaseListResponse {
  items: PurchaseListItem[];
  total: number;
  page: number;
  page_size: number;
  page_total_cny: number;
}

export interface PurchaseItemFormData {
  order_item_id: string;
  quantity: number;
  cost_price: number;
}

export interface PurchaseFormData {
  purchase_number?: string;
  supplier_id: string;
  purchase_date: string;
  currency: string;
  rate_to_cny: number;
  notes?: string;
  items: PurchaseItemFormData[];
  order_id?: string;
  total_amount?: number;
  excluded_from_accounting?: boolean;
}
