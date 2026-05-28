import { Card, Col, Row, Statistic, Typography } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";

const { Text } = Typography;

const fmt = (v: string | number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

function Delta({ pct }: { pct: number | null }) {
  if (pct === null) return null;
  const up = pct >= 0;
  return (
    <Text style={{ color: up ? "#3f8600" : "#cf1322", fontSize: 12 }}>
      {up ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(pct)}%
    </Text>
  );
}

export default function FinancesWidget({ data }: { data: any }) {
  const { t } = useTranslation();
  const profit = Number(data.profit);
  return (
    <Card title={t("dashboard.finances")} size="small">
      <Row gutter={16}>
        <Col span={12}>
          <Statistic
            title={t("dashboard.revenue")}
            value={fmt(data.revenue)}
            suffix="CNY"
            valueStyle={{ fontSize: 18 }}
          />
          <Delta pct={data.revenue_change_pct} />
        </Col>
        <Col span={12}>
          <Statistic
            title={t("dashboard.expenses_total")}
            value={fmt(data.expenses)}
            suffix="CNY"
            valueStyle={{ fontSize: 18 }}
          />
        </Col>
        <Col span={12} style={{ marginTop: 12 }}>
          <Statistic
            title={t("dashboard.purchases_paid")}
            value={fmt(data.purchases_paid)}
            suffix="CNY"
            valueStyle={{ fontSize: 18 }}
          />
        </Col>
        <Col span={12} style={{ marginTop: 12 }}>
          <Statistic
            title={t("dashboard.net_profit")}
            value={fmt(profit)}
            suffix="CNY"
            valueStyle={{ fontSize: 18, color: profit >= 0 ? "#3f8600" : "#cf1322" }}
          />
        </Col>
      </Row>
    </Card>
  );
}
