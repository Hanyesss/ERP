import client from "./client";

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body?: string;
  link?: string;
  is_read: boolean;
  created_at: string;
}

export const getUnreadCount = () =>
  client.get<{ count: number }>("/api/notifications/unread-count");

export const getNotifications = (params: { unread_only?: boolean; limit?: number; offset?: number } = {}) =>
  client.get<{ items: NotificationItem[]; total: number }>("/api/notifications", { params });

export const markRead = (id: string) =>
  client.post(`/api/notifications/${id}/mark-read`);

export const markAllRead = () =>
  client.post("/api/notifications/mark-all-read");

export const deleteNotification = (id: string) =>
  client.delete(`/api/notifications/${id}`);
