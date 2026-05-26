import apiClient from "./client";

export interface Manager {
  id: string;
  full_name: string;
  role: string;
}

export interface BusinessType {
  id: string;
  name: string;
  name_cn?: string;
  code: string;
}

export const getManagers = () =>
  apiClient.get<Manager[]>("/api/references/managers");

export const getBusinessTypes = () =>
  apiClient.get<BusinessType[]>("/api/references/business-types");
