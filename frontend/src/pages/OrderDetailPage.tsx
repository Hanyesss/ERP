import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button, Card, Col, Descriptions, Divider, Popconfirm, Row,
  Space, Statistic, Table, Tabs, Tag, Timeline, Typography, message,
} from "antd";
import { EditOutlined, CheckOutlined, CloseOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { getOrder, closeOrder, cancelOrder, getOrderHistory } from "../api/orders";
import { OrderStatusTag, PaymentStatusTag, BusinessTypeTag } from "../components/orders/OrderStatusTag";
import type { OrderItem } from "../types/order";

const { Title, Text } = Typography;

const fmtCny = (v: number) =>
  v?.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function OrderDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: order, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: () => getOrder(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: history } = useQuery({
    queryKey: ["order-history", id],
    queryFn: () => getOrderHistory(id!).then(r => r.data),
    enabled: !!id,
  });

  const closeMutation = useMutation({
    mutationFn: () => closeOrder(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      message.success(t("order.status_closed") + " ✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelOrder(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      message.success(t("order.status_cancelled") + " ✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const itemColumns: ColumnsType<OrderItem> = [
    { title: "№", key: "idx", width: 40, render: (_, __, i) => i + 1 },
    { title: t("order.item_name"), dataIndex: "name", key: "name" },
    { title: t("order.item_quantity"), dataIndex: "quantity", key: "quantity", width: 80, align: "right" },
    { title: t("order.item_unit"), dataIndex: "unit", key: "unit", width: 60 },
    { title: t("order.item_supplier"), dataIndex: "supplier_name", key: "supplier_name" },
    {
      title: t("order.item_cost_price"),
      key: "cost",
      width: 150,
      align: "right",
      render: (_, row) => `${row.cost_price} ${row.cost_currency}`,
    },
    {
      title: t("order.item_sale_price"),
      key: "sale",
      width: 150,
      align: "right",
      render: (_, row) => `${row.sale_price} ${row.sale_currency}`,
    },
    {
      title: `${t("order.total_sale")} (CNY)`,
      key: "sale_cny",
      width: 130,
      align: "right",
      render: (_, row) => fmtCny(row.quantity * row.sale_price * row.sale_rate_to_cny),
    },
    {
      title: `${t("order.total_cost")} (CNY)`,
      key: "cost_cny",
      width: 130,
      align: "right",
      render: (_, row) => fmtCny(row.quantity * row.cost_price * row.cost_rate_to_cny),
    },
  ];

  if (isLoading || !order) return null;

  const margin = order.total_sale_cny - order.total_cost_cny;
  const marginPct = order.total_sale_cny > 0 ? (margin / order.total_sale_cny) * 100 : 0;
  const canEdit = order.status === "new" || order.status === "active";
  const canClose = order.status === "new" || order.status === "active";
  const canCancel = order.status !== "cancelled" && order.status !== "closed";

  const tabItems = [
    {
      key: "main",
      label: t("order.tab_main"),
      children: (
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label={t("order.number")}>{order.order_number}</Descriptions.Item>
          <Descriptions.Item label={t("order.date")}>{order.order_date}</Descriptions.Item>
          <Descriptions.Item label={t("order.client")}>{order.client_name}</Descriptions.Item>
          <Descriptions.Item label={t("order.currency")}>{order.client_currency}</Descriptions.Item>
          <Descriptions.Item label={t("order.business_type")}>
            <BusinessTypeTag code={order.business_type_code} name={order.business_type_name} />
          </Descriptions.Item>
          <Descriptions.Item label={t("order.manager")}>{order.manager_name}</Descriptions.Item>
          <Descriptions.Item label={t("order.title")}>
            <OrderStatusTag status={order.status} />
          </Descriptions.Item>
          <Descriptions.Item label={t("order.payment_status_unpaid")}>
            <PaymentStatusTag status={order.payment_status} />
          </Descriptions.Item>
          {order.notes && (
            <Descriptions.Item label={t("order.notes")} span={2}>
              {order.notes}
            </Descriptions.Item>
          )}
        </Descriptions>
      ),
    },
    {
      key: "items",
      label: t("order.items"),
      children: (
        <>
          <Table
            columns={itemColumns}
            dataSource={order.items}
            rowKey="id"
            size="small"
            pagination={false}
          />
          <Row gutter={24} style={{ marginTop: 16 }}>
            <Col>
              <Statistic title={`${t("order.total_sale")} (CNY)`} value={fmtCny(order.total_sale_cny)} />
            </Col>
            <Col>
              <Statistic title={`${t("order.total_cost")} (CNY)`} value={fmtCny(order.total_cost_cny)} />
            </Col>
            <Col>
              <Statistic
                title={`${t("order.margin")} (CNY)`}
                value={fmtCny(margin)}
                valueStyle={{ color: margin >= 0 ? "#3f8600" : "#cf1322" }}
              />
            </Col>
            <Col>
              <Statistic
                title={t("order.margin_pct")}
                value={marginPct.toFixed(1)}
                suffix="%"
              />
            </Col>
          </Row>
        </>
      ),
    },
    {
      key: "payments",
      label: t("nav.payments") || "Платежи",
      children: (
        <div style={{ color: "#999", padding: 24, textAlign: "center" }}>
          {t("common.coming_soon") || "Раздел платежей будет добавлен в следующем модуле"}
        </div>
      ),
    },
    {
      key: "expenses",
      label: t("nav.expenses") || "Расходы",
      children: (
        <div style={{ color: "#999", padding: 24, textAlign: "center" }}>
          {t("common.coming_soon") || "Раздел расходов будет добавлен в следующем модуле"}
        </div>
      ),
    },
    {
      key: "profit",
      label: t("order.tab_profit") || "Прибыль",
      children: (
        <Row gutter={24} style={{ padding: 16 }}>
          <Col span={6}>
            <Statistic title={`${t("order.total_sale")} (CNY)`} value={fmtCny(order.total_sale_cny)} />
          </Col>
          <Col span={6}>
            <Statistic title={`${t("order.total_cost")} (CNY)`} value={fmtCny(order.total_cost_cny)} />
          </Col>
          <Col span={6}>
            <Statistic
              title={`${t("order.margin")} (CNY)`}
              value={fmtCny(margin)}
              valueStyle={{ color: margin >= 0 ? "#3f8600" : "#cf1322" }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title={t("order.margin_pct")}
              value={marginPct.toFixed(1)}
              suffix="%"
              valueStyle={{ color: marginPct >= 20 ? "#3f8600" : marginPct >= 0 ? "#faad14" : "#cf1322" }}
            />
          </Col>
        </Row>
      ),
    },
    {
      key: "history",
      label: t("order.tab_history"),
      children: (
        <Timeline
          items={(history || []).map((h: any) => ({
            children: (
              <div>
                <Text strong>{h.action}</Text>
                {" — "}
                <Text type="secondary">
                  {h.user_name} · {new Date(h.created_at).toLocaleString("ru-RU")}
                </Text>
                {h.changes && (
                  <div style={{ marginTop: 4 }}>
                    <pre style={{ fontSize: 11, margin: 0, background: "#f5f5f5", padding: 4, borderRadius: 4 }}>
                      {JSON.stringify(h.changes, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ),
          }))}
        />
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 1200 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space align="center">
            <Title level={4} style={{ margin: 0 }}>{order.order_number}</Title>
            <OrderStatusTag status={order.status} />
            <PaymentStatusTag status={order.payment_status} />
          </Space>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate("/orders")}>{t("common.back") || "Назад"}</Button>
            {canEdit && (
              <Button icon={<EditOutlined />} onClick={() => navigate(`/orders/${id}/edit`)}>
                {t("common.edit")}
              </Button>
            )}
            {canClose && (
              <Popconfirm
                title={t("order.close_confirm")}
                onConfirm={() => closeMutation.mutate()}
                okText={t("common.yes")}
                cancelText={t("common.no")}
              >
                <Button type="primary" icon={<CheckOutlined />} loading={closeMutation.isPending}>
                  {t("order.close_order")}
                </Button>
              </Popconfirm>
            )}
            {canCancel && (
              <Popconfirm
                title={t("order.cancel_confirm")}
                onConfirm={() => cancelMutation.mutate()}
                okText={t("common.yes")}
                cancelText={t("common.no")}
              >
                <Button danger icon={<CloseOutlined />} loading={cancelMutation.isPending}>
                  {t("order.cancel_order")}
                </Button>
              </Popconfirm>
            )}
          </Space>
        </Col>
      </Row>

      <Tabs items={tabItems} />
    </div>
  );
}
