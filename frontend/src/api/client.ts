import axios from "axios";

// В dev-режиме nginx на :80 проксирует на backend и корректно передаёт Set-Cookie.
// Vite proxy обрезает Set-Cookie, поэтому идём напрямую на nginx.
// CORS настроен: allow_origins=["http://localhost:5173"], allow_credentials=True.
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export default apiClient;
