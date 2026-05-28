import client from "./client";

export interface WidgetsParams {
  date_from?: string;
  date_to?: string;
}

export const getWidgets = (params: WidgetsParams = {}) =>
  client.get("/api/dashboard/widgets", { params });
