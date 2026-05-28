import axios from "axios";

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
  axios.get<Warehouse[]>("/api/warehouses", { withCredentials: true });

export const createWarehouse = (data: WarehouseCreate) =>
  axios.post<Warehouse>("/api/warehouses", data, { withCredentials: true });

export const updateWarehouse = (id: string, data: WarehouseUpdate) =>
  axios.patch<Warehouse>(`/api/warehouses/${id}`, data, { withCredentials: true });

export const deleteWarehouse = (id: string) =>
  axios.delete(`/api/warehouses/${id}`, { withCredentials: true });
