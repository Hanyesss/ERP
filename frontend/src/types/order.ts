export type OrderStatus = "new" | "active" | "closed" | "cancelled";
export type PaymentStatus = "unpaid" | "partial" | "paid";

export interface OrderItem {
  id: string;
  name: string;
  name_cn?: string;
  quantity: number;
  unit?: string;
  cost_price: number;
  cost_currency: string;
  supplier_id?: string;
  supplier_name?: string;
  sale_price: number;
  sale_currency: string;
  sale_rate_to_cny: number;
  cost_rate_to_cny: number;
}

export interface OrderItemFormData {
  name: string;
  name_cn?: string;
  quantity: number;
  unit?: string;
  cost_price: number;
  cost_currency: string;
  supplier_id?: string;
  sale_price: number;
  sale_currency: string;
}

export interface Order {
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
  total_cost_cny: number;
  payment_status: PaymentStatus;
  supplier_payment_status: PaymentStatus;
  notes?: string;
  created_at: string;
  items: OrderItem[];
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
  total_cost_cny: number;
  payment_status: PaymentStatus;
  supplier_payment_status: PaymentStatus;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
  page_total_sale_cny: number;
  page_total_cost_cny: number;
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
}
