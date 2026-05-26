import apiClient from "./client";
import type { User } from "../types";

export const login = (login: string, password: string) =>
  apiClient.post<User>("/api/auth/login", { login, password });

export const logout = () =>
  apiClient.post("/api/auth/logout");

export const getMe = () =>
  apiClient.get<User>("/api/auth/me");
