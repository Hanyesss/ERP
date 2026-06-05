import apiClient from "./client";

export interface AssetItem {
  id: string;
  name: string;
  image_path?: string;
  quantity: number;
  price: number;
  total: number;
  account?: string;
  purchase_date?: string;
  created_by_name: string;
}

export const getAssets = () =>
  apiClient.get<AssetItem[]>("/api/assets");

export const createAsset = (data: {
  name: string;
  quantity: number;
  price: number;
  account?: string;
  purchase_date?: string;
}) => apiClient.post<AssetItem>("/api/assets", data);

export const updateAsset = (id: string, data: Partial<{
  name: string;
  quantity: number;
  price: number;
  account: string;
  purchase_date: string;
}>) => apiClient.patch<AssetItem>(`/api/assets/${id}`, data);

export const deleteAsset = (id: string) =>
  apiClient.delete(`/api/assets/${id}`);

export const uploadAssetImage = (id: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.post(`/api/assets/${id}/image`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const getAssetImageUrl = (id: string) => {
  const base = import.meta.env.VITE_API_URL ?? "";
  return `${base}/api/assets/${id}/image`;
};
