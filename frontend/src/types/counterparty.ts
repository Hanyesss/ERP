export type CounterpartyType = "client" | "supplier" | "both" | "partner";
export type CurrencyEnum = "CNY" | "RUB" | "USDT";

export interface ContactInfo {
  phone?: string;
  email?: string;
  address?: string;
}

export interface Counterparty {
  id: string;
  name: string;
  name_cn?: string;
  code?: string;
  type: CounterpartyType;
  default_currency: CurrencyEnum;
  contact_info?: ContactInfo;
  phone?: string;
  notes?: string;
  is_active: boolean;
  partner_id?: string;
  partner_name?: string;
  is_logistics?: boolean;
}

export interface CounterpartyListResponse {
  items: Counterparty[];
  total: number;
  page: number;
  page_size: number;
}

export interface CounterpartyFormData {
  name: string;
  name_cn?: string;
  code?: string;
  type: CounterpartyType;
  default_currency: CurrencyEnum;
  phone?: string;
  email?: string;
  address?: string;
  notes?: string;
  partner_id?: string;
  is_logistics?: boolean;
}
