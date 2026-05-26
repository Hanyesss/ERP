import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import ruRU from "antd/locale/ru_RU";
import zhCN from "antd/locale/zh_CN";
import { useTranslation } from "react-i18next";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuth } from "./hooks/useAuth";

export default function App() {
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
            path="/dashboard"
            element={
              <ProtectedRoute user={user} loading={loading}>
                <DashboardPage user={user!} onLogout={() => setUser(null)} />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
