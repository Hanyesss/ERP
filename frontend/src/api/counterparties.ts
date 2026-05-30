import apiClient from "./client";
import type { Counterparty, CounterpartyListResponse, CounterpartyFormData } from "../types/counterparty";

export interface ListParams {
  search?: string;
  type?: string;
  page?: number;
  page_size?: number;
}

export const getCounterparties = (params: ListParams = {}) =>
  apiClient.get<CounterpartyListResponse>("/api/counterparties", { params });

export const getCounterparty = (id: string) =>
  apiClient.get<Counterparty>(`/api/counterparties/${id}`);

export const createCounterparty = (data: CounterpartyFormData) => {
  const { phone, email, address, ...rest } = data;
  const contact_info = (phone || email || address) ? { phone, email, address } : undefined;
  return apiClient.post<Counterparty>("/api/counterparties", { ...rest, contact_info });
};

export const updateCounterparty = (id: string, data: Partial<CounterpartyFormData>) => {
  const { phone, email, address, ...rest } = data;
  const contact_info = (phone !== undefined || email !== undefined || address !== undefined)
    ? { phone, email, address }
    : undefined;
  const payload = contact_info !== undefined ? { ...rest, contact_info } : rest;
  return apiClient.patch<Counterparty>(`/api/counterparties/${id}`, payload);
};

export const deleteCounterparty = (id: string) =>
  apiClient.delete(`/api/counterparties/${id}`);

export const createSiteAccount = (id: string, data: { login: string; password: string }) =>
  apiClient.post(`/api/counterparties/${id}/create-site-account`, data);
