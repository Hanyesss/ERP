import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button, Card, Col, Descriptions, Divider, Popconfirm, Row,
  Space, Table, Tag, Typography, message,
} from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { getPurchase, deletePurchase } from "../api/purchases";

const { Title, Text } = Typography;

const STATUS_COLORS: Record<string, string> = { unpaid: "red", partial: "orange", paid: "green" };

const fmtCny = (v: number | null | undefined) =>
  v != null ? v.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

export default function PurchaseDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: purchase, isLoading } = useQuery({
    queryKey: ["purchase", id],
    queryFn: () => getPurchase(id!).then(r => r.data),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePurchase(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["purchases"] });
      message.success("✓");
      navigate("/purchases");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  if (isLoading || !purchase) return null;

  return (
    <div style={{ maxWidth: 900 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space align="center">
            <Title level={4} style={{ margin: 0 }}>{purchase.purchase_number}</Title>
            <Tag color={STATUS_COLORS[purchase.payment_status]}>
              {t(`purchase.status_${purchase.payment_status}`)}
            </Tag>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate("/purchases")}>{t("common.back")}</Button>
            {purchase.payment_status !== "paid" && (
              <Popconfirm
                title={t("purchase.delete_confirm")}
                onConfirm={() => deleteMutation.mutate()}
                okText={t("common.yes")}
                cancelText={t("common.no")}
              >
                <Button danger icon={<DeleteOutlined />} loading={deleteMutation.isPending}>
                  {t("common.delete")}
                </Button>
              </Popconfirm>
            )}
          </Space>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label={t("purchase.number")}>{purchase.purchase_number}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.date")}>{purchase.purchase_date}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.supplier")}>{purchase.supplier_name}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.currency")}>{purchase.currency}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.rate_to_cny")}>{Number(purchase.rate_to_cny).toFixed(4)}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.payment_status")}>
            <Tag color={STATUS_COLORS[purchase.payment_status]}>{t(`purchase.status_${purchase.payment_status}`)}</Tag>
          </Descriptions.Item>
          {purchase.notes && (
            <Descriptions.Item label={t("purchase.notes")} span={2}>{purchase.notes}</Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card title={t("purchase.items")}>
        <Table
          dataSource={purchase.items}
          rowKey="id"
          size="small"
          pagination={false}
          columns={[
            { title: t("order.title"), dataIndex: "order_number", key: "order_num",
              render: (num, row: any) => (
                <Button type="link" size="small" onClick={() => {
                  // Navigate to order by finding via order_item_id — we use order_number link
                }}>
                  {num}
                </Button>
              )
            },
            { title: t("order.item_name"), dataIndex: "order_item_name", key: "name" },
            { title: t("order.item_quantity"), dataIndex: "quantity", key: "qty", align: "right" },
            {
              title: `${t("purchase.cost_price")} (${purchase.currency})`,
              dataIndex: "cost_price", key: "cost_price", align: "right",
              render: v => fmtCny(v),
            },
            {
              title: `${t("purchase.total")} (${purchase.currency})`,
              key: "total", align: "right",
              render: (_, row: any) => fmtCny(Number(row.quantity) * Number(row.cost_price)),
            },
            { title: `${t("purchase.cost_amount_cny")} CNY`, dataIndex: "cost_amount", key: "cny", align: "right",
              render: v => fmtCny(v) },
          ]}
          summary={() => (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={4} align="right">
                <strong>{t("purchase.total")} ({purchase.currency}):</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={4} align="right">
                <strong>{fmtCny(purchase.total_amount)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={5} align="right">
                <strong>{fmtCny(purchase.total_amount_cny)}</strong>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      </Card>
    </div>
  );
}
