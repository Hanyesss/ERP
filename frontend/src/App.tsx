import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import ruRU from "antd/locale/ru_RU";
import zhCN from "antd/locale/zh_CN";
import { useTranslation } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import CounterpartiesPage from "./pages/CounterpartiesPage";
import AppLayout from "./components/layout/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./hooks/useAuth";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function Inner() {
  const { i18n } = useTranslation();
  const { user, setUser, loading } = useAuth();
  const antLocale = i18n.language === "zh" ? zhCN : ruRU;

  return (
    <ConfigProvider locale={antLocale}>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              !loading && user
                ? <Navigate to="/dashboard" replace />
                : <LoginPage onLogin={setUser} />
            }
          />
          <Route
            element={
              <ProtectedRoute user={user} loading={loading}>
                <AppLayout user={user!} onLogout={() => setUser(null)} />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage user={user!} />} />
            <Route path="/counterparties" element={<CounterpartiesPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Inner />
    </QueryClientProvider>
  );
}
