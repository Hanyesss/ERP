export type OrderStatus = "new" | "active" | "closed" | "cancelled";
export type PaymentStatus = "unpaid" | "partial" | "paid";

export interface OrderCharge {
  id: string;
  charge_type: string;
  amount: number;
  currency: string;
  amount_cny: number;
  rate_to_cny: number;
  notes?: string;
}

export interface PurchaseItemBrief {
  id: string;
  purchase_id: string;
  purchase_number: string;
  quantity: number;
  cost_price: number;
  cost_amount: number;
}

export interface OrderItem {
  id: string;
  name: string;
  name_cn?: string;
  quantity?: number;
  unit?: string;
  preferred_supplier_id?: string;
  preferred_supplier_name?: string;
  sale_price?: number;
  sale_currency?: string;
  sale_rate_to_cny?: number;
  // Logistics
  weight_kg?: number;
  volume_m3?: number;
  density_kg_m3?: number;
  price_per_kg?: number;
  price_per_kg_currency?: string;
  cargo_value?: number;
  cargo_value_currency?: string;
  places_count?: number;
  // Purchase data (visible to purchaser/accountant/admin)
  purchased_quantity?: number;
  purchase_items?: PurchaseItemBrief[];
}

export interface OrderItemFormData {
  name: string;
  name_cn?: string;
  // Trade
  quantity?: number;
  unit?: string;
  preferred_supplier_id?: string;
  sale_price?: number;
  sale_currency?: string;
  // Logistics
  weight_kg?: number;
  volume_m3?: number;
  price_per_kg?: number;
  price_per_kg_currency?: string;
  cargo_value?: number;
  cargo_value_currency?: string;
  places_count?: number;
}

export interface OrderChargeFormData {
  charge_type: string;
  amount?: number;
  currency: string;
  notes?: string;
}

export interface OrderFile {
  id: string;
  order_id: string;
  file_url: string;
  file_name: string;
  file_type: string;
  file_size_bytes?: number;
  mime_type?: string;
  uploaded_by: string;
  uploaded_by_name: string;
  uploaded_at: string;
}

export interface Order {
  id: string;
  order_number: string;
  order_date: string;
  client_id: string;
  client_name: string;
  business_type_id: string;
  business_type_name: string;
  business_type_name_cn?: string;
  business_type_code: string;
  manager_id: string;
  manager_name: string;
  status: OrderStatus;
  client_currency: string;
  total_sale_cny: number;
  total_cost_cny?: number;
  expenses_cny?: number;
  payment_status: PaymentStatus;
  supplier_payment_status?: PaymentStatus;
  paid_amount_cny: number;
  remaining_amount_cny: number;
  notes?: string;
  recipient?: string;
  destination?: string;
  arrival_date?: string;
  tracking_number?: string;
  warehouse_id?: string;
  warehouse_name?: string;
  created_at: string;
  items: OrderItem[];
  charges: OrderCharge[];
  // Sync fields
  external_shipment_id?: string;
  external_shipment_number?: string;
  external_invoice_url?: string;
  external_tracking_url?: string;
  sync_status?: string;
  sync_error?: string;
  synced_at?: string;
}

export interface OrderListItem {
  id: string;
  order_number: string;
  order_date: string;
  client_id: string;
  client_name: string;
  business_type_id: string;
  business_type_name: string;
  business_type_code: string;
  manager_id: string;
  manager_name: string;
  status: OrderStatus;
  client_currency: string;
  total_sale_cny: number;
  total_cost_cny?: number;
  payment_status: PaymentStatus;
  supplier_payment_status?: PaymentStatus;
  paid_amount_cny: number;
  remaining_amount_cny: number;
  sync_status?: string;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
  page_total_sale_cny: number;
  page_total_cost_cny?: number;
}

export interface OrderFormData {
  order_number: string;
  order_date: string;
  client_id: string;
  business_type_id: string;
  manager_id: string;
  client_currency: string;
  notes?: string;
  items: OrderItemFormData[];
  charges: OrderChargeFormData[];
  recipient?: string;
  destination?: string;
  arrival_date?: string;
  tracking_number?: string;
}

export interface AvailableForPurchaseItem {
  id: string;
  name: string;
  name_cn?: string;
  quantity?: number;
  unit?: string;
  sale_price?: number;
  sale_currency?: string;
  preferred_supplier_id?: string;
  preferred_supplier_name?: string;
  already_purchased: number;
  available_to_purchase: number;
}
