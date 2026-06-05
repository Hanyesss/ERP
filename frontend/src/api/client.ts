import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.response.use(
  r => r,
  error => {
    const url: string = error.config?.url ?? "";
    if (error.response?.status === 401 && !url.includes("/api/auth/")) {
      window.location.replace("/login");
    }
    return Promise.reject(error);
  }
);

export default apiClient;
