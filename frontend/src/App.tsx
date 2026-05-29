import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import ruRU from "antd/locale/ru_RU";
import zhCN from "antd/locale/zh_CN";
import { useTranslation } from "react-i18next";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import CounterpartiesPage from "./pages/CounterpartiesPage";
import OrdersPage from "./pages/OrdersPage";
import OrderFormPage from "./pages/OrderFormPage";
import OrderDetailPage from "./pages/OrderDetailPage";
import ExchangeRatesPage from "./pages/ExchangeRatesPage";
import PurchasesPage from "./pages/PurchasesPage";
import PurchaseFormPage from "./pages/PurchaseFormPage";
import PurchaseDetailPage from "./pages/PurchaseDetailPage";
import PaymentsPage from "./pages/PaymentsPage";
import PaymentFormPage from "./pages/PaymentFormPage";
import PaymentDetailPage from "./pages/PaymentDetailPage";
import ExpensesPage from "./pages/ExpensesPage";
import ExpenseFormPage from "./pages/ExpenseFormPage";
import ExpenseDetailPage from "./pages/ExpenseDetailPage";
import WarehousesPage from "./pages/WarehousesPage";
import ReportsPage from "./pages/reports/ReportsPage";
import UsersPage from "./pages/UsersPage";
import NotificationsPage from "./pages/NotificationsPage";
import IntegrationSettingsPage from "./pages/IntegrationSettingsPage";
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
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/new" element={<OrderFormPage user={user!} />} />
            <Route path="/orders/:id" element={<OrderDetailPage />} />
            <Route path="/orders/:id/edit" element={<OrderFormPage user={user!} />} />
            <Route path="/exchange-rates" element={<ExchangeRatesPage />} />
            <Route path="/purchases" element={<PurchasesPage />} />
            <Route path="/purchases/new" element={<PurchaseFormPage />} />
            <Route path="/purchases/:id" element={<PurchaseDetailPage />} />
            <Route path="/payments" element={<PaymentsPage />} />
            <Route path="/payments/new" element={<PaymentFormPage />} />
            <Route path="/payments/:id" element={<PaymentDetailPage />} />
            <Route path="/expenses" element={<ExpensesPage user={user!} />} />
            <Route path="/expenses/new" element={<ExpenseFormPage user={user!} />} />
            <Route path="/expenses/:id" element={<ExpenseDetailPage user={user!} />} />
            <Route path="/expenses/:id/edit" element={<ExpenseFormPage user={user!} />} />
            <Route path="/warehouses" element={<WarehousesPage />} />
            <Route path="/reports" element={<ReportsPage user={user!} />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/settings/integrations" element={<IntegrationSettingsPage />} />
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
