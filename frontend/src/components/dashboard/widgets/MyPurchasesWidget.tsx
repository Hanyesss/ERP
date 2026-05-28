import { Card, Row, Col, Statistic, Table, Button, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

const { Text } = Typography;
const fmt = (v: string | number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export default function MyPurchasesWidget({
  purchases, needsPurchase, topSuppliers,
}: { purchases: any; needsPurchase: any[]; topSuppliers: any[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <>
      <Card title={t("dashboard.my_purchases")} size="small">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title={t("dashboard.count")} value={purchases.count} valueStyle={{ fontSize: 20 }} />
          </Col>
          <Col span={8}>
            <Statistic title={t("dashboard.total_cny")} value={fmt(purchases.total_cny)} suffix="CNY" valueStyle={{ fontSize: 16 }} />
          </Col>
          <Col span={8}>
            <Statistic
              title={t("dashboard.supplier_debt")}
              value={fmt(purchases.supplier_debt)}
              suffix="CNY"
              valueStyle={{ fontSize: 16, color: "#faad14" }}
            />
          </Col>
        </Row>
      </Card>

      <Card
        title={t("dashboard.needs_purchase")}
        size="small"
        style={{ marginTop: 16 }}
        extra={<Text type="secondary" style={{ fontSize: 12 }}>{needsPurchase.length} {t("dashboard.orders")}</Text>}
      >
        <Table
          dataSource={needsPurchase}
          rowKey="order_id"
          size="small"
          pagination={{ pageSize: 5, simple: true }}
          onRow={row => ({ onClick: () => navigate(`/orders/${row.order_id}`) })}
          columns={[
            { title: t("order.number"), dataIndex: "order_number", key: "num",
              render: v => <Button type="link" style={{ padding: 0 }}>{v}</Button> },
            { title: t("order.client"), dataIndex: "client", key: "client" },
            { title: t("dashboard.remaining_qty"), dataIndex: "remaining_qty", key: "qty", align: "right",
              render: v => Number(v).toFixed(0) },
          ]}
        />
      </Card>

      <Card title={t("dashboard.top_suppliers")} size="small" style={{ marginTop: 16 }}>
        <Table
          dataSource={topSuppliers}
          rowKey="supplier"
          size="small"
          pagination={false}
          columns={[
            { title: t("purchase.supplier"), dataIndex: "supplier", key: "s" },
            { title: "CNY", dataIndex: "total", key: "t", align: "right", render: v => fmt(v) },
          ]}
        />
      </Card>
    </>
  );
}
