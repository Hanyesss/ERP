import apiClient from "./client";

export interface SupplierQuote {
  id: string;
  supplier_id: string;
  supplier_name: string;
  price: number;
  price_unit: "per_kg" | "per_cbm";
  currency: string;
  delivery_days?: string | null;
  insurance_pct?: number | null;
  notes?: string | null;
  created_by_name: string;
}

export interface QuoteRequest {
  id: string;
  order_id?: string | null;
  order_number?: string | null;
  product_name?: string | null;
  cargo_value?: string | null;
  box?: string | null;
  dimensions?: string | null;
  volume_m3?: number | null;
  weight_kg?: number | null;
  density?: number | null;
  destination?: string | null;
  dispatch_place?: string | null;
  notes?: string | null;
  selected_quote_id?: string | null;
  selected_by_name?: string | null;
  selected_at?: string | null;
  created_by_name?: string | null;
  created_at?: string | null;
  quotes: SupplierQuote[];
  selected_total?: number | null;
}

export interface QuoteRequestInput {
  order_id?: string;
  order_number?: string;
  product_name?: string;
  cargo_value?: string;
  box?: string;
  dimensions?: string;
  volume_m3?: number;
  weight_kg?: number;
  destination?: string;
  dispatch_place?: string;
  notes?: string;
}

export interface SupplierQuoteInput {
  supplier_id: string;
  price: number;
  price_unit: "per_kg" | "per_cbm";
  currency: string;
  delivery_days?: string;
  insurance_pct?: number;
  notes?: string;
}

export const getQuoteRequests = (params?: { search?: string; order_id?: string; only_unselected?: boolean }) =>
  apiClient.get<QuoteRequest[]>("/api/logistics-quotes/requests", { params });

export const createQuoteRequest = (data: QuoteRequestInput) =>
  apiClient.post<QuoteRequest>("/api/logistics-quotes/requests", data);

export const updateQuoteRequest = (id: string, data: Partial<QuoteRequestInput>) =>
  apiClient.patch<QuoteRequest>(`/api/logistics-quotes/requests/${id}`, data);

export const deleteQuoteRequest = (id: string) =>
  apiClient.delete(`/api/logistics-quotes/requests/${id}`);

export const addSupplierQuote = (requestId: string, data: SupplierQuoteInput) =>
  apiClient.post<QuoteRequest>(`/api/logistics-quotes/requests/${requestId}/quotes`, data);

export const updateSupplierQuote = (quoteId: string, data: Partial<SupplierQuoteInput>) =>
  apiClient.patch<QuoteRequest>(`/api/logistics-quotes/quotes/${quoteId}`, data);

export const deleteSupplierQuote = (quoteId: string) =>
  apiClient.delete(`/api/logistics-quotes/quotes/${quoteId}`);

export const selectQuote = (requestId: string, quoteId: string) =>
  apiClient.post<QuoteRequest>(`/api/logistics-quotes/requests/${requestId}/select`, { quote_id: quoteId });

export const unselectQuote = (requestId: string) =>
  apiClient.post<QuoteRequest>(`/api/logistics-quotes/requests/${requestId}/unselect`, {});
