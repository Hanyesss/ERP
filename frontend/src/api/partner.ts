import apiClient from "./client";
import type {
  PartnerSummary, PartnerOrder, PartnerClient, PartnerPayout, AdminPartner,
} from "../types";

export const getPartnerSummary = () =>
  apiClient.get<PartnerSummary>("/api/partner/summary");

export const getPartnerOrders = () =>
  apiClient.get<PartnerOrder[]>("/api/partner/orders");

export const getPartnerClients = () =>
  apiClient.get<PartnerClient[]>("/api/partner/clients");

export const requestPayout = (data: { period_from?: string; period_to?: string; notes?: string }) =>
  apiClient.post<PartnerPayout>("/api/partner/payout-request", data);

export const getPartnerPayouts = () =>
  apiClient.get<PartnerPayout[]>("/api/partner/payouts");

export const getAdminPartnerPayouts = () =>
  apiClient.get<PartnerPayout[]>("/api/admin/partner-payouts");

export const updateAdminPartnerPayout = (id: string, data: { status: string }) =>
  apiClient.patch<PartnerPayout>(`/api/admin/partner-payouts/${id}`, data);

export const getAdminPartners = () =>
  apiClient.get<AdminPartner[]>("/api/admin/partners");
