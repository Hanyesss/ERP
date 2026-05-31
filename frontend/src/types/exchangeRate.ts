export interface ExchangeRate {
  id: string;
  currency: "RUB" | "USDT" | "USD";
  rate_to_cny: number;
  rate_date: string;
  created_by: string;
  created_by_name: string;
  source: "auto" | "manual";
  created_at: string;
}

export interface ExchangeRateListResponse {
  items: ExchangeRate[];
  total: number;
}

export interface RateCheckResponse {
  rates: Record<string, number>;
  missing: string[];
}
