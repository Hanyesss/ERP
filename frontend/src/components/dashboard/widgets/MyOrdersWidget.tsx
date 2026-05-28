import { Card, Row, Col, Statistic, Table, Tag, Button } from "antd";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

const fmt = (v: string | number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const STATUS_COLOR: Record<string, string> = {
  new: "blue", active: "orange", closed: "green",
};

export default function MyOrdersWidget({ data, recent }: { data: any; recent: any[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <>
      <Card title={t("dashboard.my_orders")} size="small">
        <Row gutter={12}>
          <Col span={8}>
            <Statistic title={t("order.status_new")} value={data.new} valueStyle={{ fontSize: 20 }} />
          </Col>
          <Col span={8}>
            <Statistic title={t("order.status_active")} value={data.active} valueStyle={{ fontSize: 20, color: "#faad14" }} />
          </Col>
          <Col span={8}>
            <Statistic title={t("order.status_closed")} value={data.closed} valueStyle={{ fontSize: 20, color: "#3f8600" }} />
          </Col>
          <Col span={12} style={{ marginTop: 12 }}>
            <Statistic title={t("dashboard.my_revenue")} value={fmt(data.revenue)} suffix="CNY" valueStyle={{ fontSize: 16 }} />
          </Col>
          <Col span={12} style={{ marginTop: 12 }}>
            <Statistic
              title={t("dashboard.clients_owe_us")}
              value={fmt(data.client_debt)}
              suffix="CNY"
              valueStyle={{ fontSize: 16, color: "#cf1322" }}
            />
          </Col>
        </Row>
      </Card>

      <Card title={t("dashboard.recent_orders")} size="small" style={{ marginTop: 16 }}>
        <Table
          dataSource={recent}
          rowKey="id"
          size="small"
          pagination={false}
          onRow={row => ({ onClick: () => navigate(`/orders/${row.id}`) })}
          columns={[
            { title: t("order.number"), dataIndex: "order_number", key: "num",
              render: v => <Button type="link" style={{ padding: 0 }}>{v}</Button> },
            { title: t("order.client"), dataIndex: "client", key: "client" },
            { title: t("order.date"), dataIndex: "order_date", key: "date", width: 90 },
            { title: "", dataIndex: "status", key: "status", width: 80,
              render: (s: string) => <Tag color={STATUS_COLOR[s] || "default"}>{t(`order.status_${s}`)}</Tag> },
          ]}
        />
      </Card>
    </>
  );
}
