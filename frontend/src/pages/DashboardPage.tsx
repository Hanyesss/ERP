import { Col, Row, Statistic, Card, Typography } from "antd";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import type { User } from "../types";
import { getDashboardBalances } from "../api/payments";
import { useHasAnyRole } from "../hooks/useRole";

interface Props {
  user: User;
}

const fmtCny = (v: string | number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function DashboardPage({ user }: Props) {
  const { t } = useTranslation();
  const canSeeBalances = useHasAnyRole("accountant", "admin");

  const { data: balances } = useQuery({
    queryKey: ["dashboard-balances"],
    queryFn: () => getDashboardBalances().then(r => r.data),
    enabled: canSeeBalances,
  });

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 24 }}>
        {t("dashboard.welcome")}, {user.full_name}
      </Typography.Title>

      {canSeeBalances && (
        <Row gutter={16}>
          <Col xs={24} sm={12} md={8}>
            <Card>
              <Statistic
                title={t("dashboard.accounts_receivable")}
                value={fmtCny(balances?.total_receivable_cny ?? 0)}
                suffix="CNY"
                valueStyle={{ color: Number(balances?.total_receivable_cny ?? 0) > 0 ? "#cf1322" : "#3f8600" }}
              />
              {balances && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t("dashboard.unpaid_orders")}: {balances.unpaid_orders_count}
                </Typography.Text>
              )}
            </Card>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Card>
              <Statistic
                title={t("dashboard.accounts_payable")}
                value={fmtCny(balances?.total_payable_cny ?? 0)}
                suffix="CNY"
                valueStyle={{ color: Number(balances?.total_payable_cny ?? 0) > 0 ? "#faad14" : "#3f8600" }}
              />
              {balances && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t("dashboard.unpaid_purchases")}: {balances.unpaid_purchases_count}
                </Typography.Text>
              )}
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
