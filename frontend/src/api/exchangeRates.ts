import apiClient from "./client";
import type { ExchangeRateListResponse, RateCheckResponse } from "../types/exchangeRate";

export const getExchangeRates = (params?: { currency?: string; date_from?: string; date_to?: string }) =>
  apiClient.get<ExchangeRateListResponse>("/api/exchange-rates", { params });

export const createExchangeRate = (data: { currency: string; rate_to_cny: number; rate_date: string }) =>
  apiClient.post("/api/exchange-rates", data);

export const checkExchangeRates = (date: string, currencies: string[]) =>
  apiClient.get<RateCheckResponse>("/api/exchange-rates/check", {
    params: { date, currencies: currencies.join(",") },
  });
