import apiClient from "./client";

export interface Warehouse {
  id: string;
  name: string;
  name_cn?: string;
  city?: string;
  is_active: boolean;
}

export interface WarehouseCreate {
  name: string;
  name_cn?: string;
  city?: string;
  is_active?: boolean;
}

export interface WarehouseUpdate {
  name?: string;
  name_cn?: string;
  city?: string;
  is_active?: boolean;
}

export const getWarehouses = () =>
  apiClient.get<Warehouse[]>("/api/warehouses");

export const createWarehouse = (data: WarehouseCreate) =>
  apiClient.post<Warehouse>("/api/warehouses", data);

export const updateWarehouse = (id: string, data: WarehouseUpdate) =>
  apiClient.patch<Warehouse>(`/api/warehouses/${id}`, data);

export const deleteWarehouse = (id: string) =>
  apiClient.delete(`/api/warehouses/${id}`);
