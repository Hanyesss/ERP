import client from "./client";

export type UserRole = "employee" | "manager" | "purchaser" | "accountant" | "admin";
export type UserLang = "ru" | "zh";

export interface UserListItem {
  id: string;
  full_name: string;
  login: string;
  roles: UserRole[];
  lang: UserLang;
  is_active: boolean;
}

export interface UserCreate {
  full_name: string;
  login: string;
  password: string;
  lang: UserLang;
  roles: UserRole[];
  is_active: boolean;
}

export interface UserUpdate {
  full_name?: string;
  lang?: UserLang;
  roles?: UserRole[];
  is_active?: boolean;
}

export interface ResetPasswordBody {
  password?: string;
}

export interface ResetPasswordResponse {
  new_password: string;
}

export interface UsersFilter {
  role?: string;
  is_active?: boolean;
  search?: string;
}

export async function fetchUsers(filter: UsersFilter = {}): Promise<UserListItem[]> {
  const params: Record<string, string> = {};
  if (filter.role) params.role = filter.role;
  if (filter.is_active !== undefined) params.is_active = String(filter.is_active);
  if (filter.search) params.search = filter.search;
  const res = await client.get("/api/users", { params });
  return res.data;
}

export async function fetchUser(id: string): Promise<UserListItem> {
  const res = await client.get(`/api/users/${id}`);
  return res.data;
}

export async function createUser(data: UserCreate): Promise<UserListItem> {
  const res = await client.post("/api/users", data);
  return res.data;
}

export async function updateUser(id: string, data: UserUpdate): Promise<UserListItem> {
  const res = await client.patch(`/api/users/${id}`, data);
  return res.data;
}

export async function resetPassword(
  id: string,
  body: ResetPasswordBody
): Promise<ResetPasswordResponse> {
  const res = await client.post(`/api/users/${id}/reset-password`, body);
  return res.data;
}

export async function toggleActive(id: string): Promise<UserListItem> {
  const res = await client.post(`/api/users/${id}/toggle-active`);
  return res.data;
}

export async function deleteUser(id: string): Promise<void> {
  await client.delete(`/api/users/${id}`);
}
