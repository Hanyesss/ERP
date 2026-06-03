import apiClient from "./client";

export interface WarehouseBox {
  id: string;
  box_code: string;
  counterparty_id: string;
  counterparty_code: string | null;
  counterparty_name: string | null;
  warehouse_id: string;
  weight: number;
  volume: number;
  density: number;
  item_name: string;
  description: string | null;
  photo_url: string | null;
  status: "on_warehouse" | "shipped";
  received_at: string | null;
  shipped_at: string | null;
}

export interface ClientGroup {
  counterparty_id: string;
  counterparty_code: string;
  counterparty_name: string;
  sum_weight: number;
  sum_volume: number;
  total_density: number;
  boxes_count: number;
  boxes: WarehouseBox[];
}

export interface BoxCreate {
  counterparty_id: string;
  warehouse_id: string;
  weight: number;
  volume: number;
  item_name: string;
  description?: string;
}

export interface BoxUpdate {
  weight?: number;
  volume?: number;
  item_name?: string;
  description?: string;
}

export const getBalance = (params?: { warehouse_id?: string; search?: string }) =>
  apiClient.get<ClientGroup[]>("/api/warehouse-boxes/balance", { params });

export const getShipped = (params?: { warehouse_id?: string }) =>
  apiClient.get<WarehouseBox[]>("/api/warehouse-boxes/shipped", { params });

export const createBox = (data: BoxCreate) =>
  apiClient.post<WarehouseBox>("/api/warehouse-boxes", data);

export const updateBox = (id: string, data: BoxUpdate) =>
  apiClient.patch<WarehouseBox>(`/api/warehouse-boxes/${id}`, data);

export const deleteBox = (id: string) =>
  apiClient.delete(`/api/warehouse-boxes/${id}`);

export const uploadBoxPhoto = (boxId: string, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return apiClient.post<{ photo_url: string; photo_path: string }>(
    `/api/warehouse-boxes/${boxId}/photo`,
    fd,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
};

export const getQrLabelUrl = (boxId: string) =>
  `/api/warehouse-boxes/${boxId}/qr`;

export const generatePackingListPreview = (boxIds: string[]) =>
  apiClient.post(
    "/api/warehouse-boxes/packing-list",
    { box_ids: boxIds },
    { responseType: "blob" }
  );

export const shipBoxes = (boxCodes: string[]) =>
  apiClient.post(
    "/api/warehouse-boxes/ship",
    { box_codes: boxCodes },
    { responseType: "blob" }
  );

export interface PackingListRecord {
  id: string;
  created_at: string;
  total_boxes: number | null;
  total_weight: number | null;
  total_volume: number | null;
  pdf_url: string | null;
  box_count: number;
  clients: string[];
}

export const getPackingLists = () =>
  apiClient.get<PackingListRecord[]>("/api/warehouse-boxes/packing-lists");

export const getPackingListPdfUrl = (pdfUrl: string) =>
  (import.meta.env.VITE_API_URL ?? "") + pdfUrl;

export const checkBoxCode = (boxCode: string) =>
  apiClient.get<{ found: boolean; status: string | null; box_code: string }>(
    `/api/warehouse-boxes/check/${encodeURIComponent(boxCode)}`
  );
