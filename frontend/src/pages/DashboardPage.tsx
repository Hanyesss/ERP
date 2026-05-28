import { useState } from "react";
import { Col, Row, Spin, Typography } from "antd";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import type { User } from "../types";
import { getWidgets } from "../api/dashboard";
import { useHasAnyRole } from "../hooks/useRole";
import PeriodPicker, { type Period } from "../components/dashboard/PeriodPicker";
import FinancesWidget from "../components/dashboard/widgets/FinancesWidget";
import ProfitChartWidget from "../components/dashboard/widgets/ProfitChartWidget";
import DebtsWidget from "../components/dashboard/widgets/DebtsWidget";
import TopClientsWidget from "../components/dashboard/widgets/TopClientsWidget";
import ExpenseStructureWidget from "../components/dashboard/widgets/ExpenseStructureWidget";
import TonnageWidget from "../components/dashboard/widgets/TonnageWidget";
import MyOrdersWidget from "../components/dashboard/widgets/MyOrdersWidget";
import MyPurchasesWidget from "../components/dashboard/widgets/MyPurchasesWidget";
import MyReimbursementsWidget from "../components/dashboard/widgets/MyReimbursementsWidget";

interface Props { user: User }

const today = dayjs().format("YYYY-MM-DD");
const monthStart = dayjs().startOf("month").format("YYYY-MM-DD");

export default function DashboardPage({ user }: Props) {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<Period>({ date_from: monthStart, date_to: today });

  const isAdminOrAccountant = useHasAnyRole("admin", "accountant");
  const isManager = useHasAnyRole("manager");
  const isPurchaser = useHasAnyRole("purchaser");
  const isEmployee = useHasAnyRole("employee");
  const isOnlyEmployee = isEmployee && !isAdminOrAccountant && !isManager && !isPurchaser;

  const { data: widgets, isLoading } = useQuery({
    queryKey: ["dashboard-widgets", period],
    queryFn: () => getWidgets(period).then(r => r.data),
    staleTime: 60_000,
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t("dashboard.welcome")}, {user.full_name}
        </Typography.Title>
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>

      {isLoading && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin size="large" />
        </div>
      )}

      {!isLoading && widgets && (
        <Row gutter={[16, 16]}>

          {/* ── Admin / Accountant ── */}
          {isAdminOrAccountant && widgets.finances && (
            <Col xs={24} lg={12}>
              <FinancesWidget data={widgets.finances} />
            </Col>
          )}
          {isAdminOrAccountant && widgets.debts && (
            <Col xs={24} lg={12}>
              <DebtsWidget data={widgets.debts} />
            </Col>
          )}
          {isAdminOrAccountant && widgets.profit_dynamics && (
            <Col xs={24} lg={16}>
              <ProfitChartWidget data={widgets.profit_dynamics} />
            </Col>
          )}
          {isAdminOrAccountant && widgets.expense_structure?.length > 0 && (
            <Col xs={24} lg={8}>
              <ExpenseStructureWidget data={widgets.expense_structure} />
            </Col>
          )}
          {isAdminOrAccountant && widgets.top_clients?.length > 0 && (
            <Col xs={24} md={12} lg={8}>
              <TopClientsWidget data={widgets.top_clients} />
            </Col>
          )}

          {/* ── Tonnage (manager + admin + accountant) ── */}
          {widgets.tonnage !== undefined && (
            <Col xs={24} md={12} lg={8}>
              <TonnageWidget data={widgets.tonnage} />
            </Col>
          )}

          {/* ── Manager ── */}
          {isManager && widgets.my_orders && (
            <Col xs={24} lg={12}>
              <MyOrdersWidget data={widgets.my_orders} recent={widgets.recent_orders || []} />
            </Col>
          )}

          {/* ── Purchaser ── */}
          {isPurchaser && widgets.my_purchases && (
            <Col xs={24} lg={12}>
              <MyPurchasesWidget
                purchases={widgets.my_purchases}
                needsPurchase={widgets.needs_purchase || []}
                topSuppliers={widgets.top_suppliers || []}
              />
            </Col>
          )}

          {/* ── Employee ── */}
          {(isOnlyEmployee || isEmployee) && widgets.my_reimbursements && (
            <Col xs={24} md={12} lg={8}>
              <MyReimbursementsWidget data={widgets.my_reimbursements} />
            </Col>
          )}
        </Row>
      )}
    </div>
  );
}
