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
  notes?: string;
  created_at: string;
  items: PurchaseItem[];
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
}
