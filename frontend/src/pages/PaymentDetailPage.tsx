import { useNavigate, useParams } from "react-router-dom";
import {
  Button, Card, Col, Descriptions, Divider, Popconfirm, Row,
  Space, Statistic, Table, Tag, Typography, message,
} from "antd";
import { DeleteOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getPayment, deletePayment } from "../api/payments";

const { Title, Text } = Typography;

const fmtCny = (v: number | string | null | undefined) =>
  v != null ? Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2 }) : "—";

export default function PaymentDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: payment, isLoading } = useQuery({
    queryKey: ["payment", id],
    queryFn: () => getPayment(id!).then(r => r.data),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePayment(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["purchases"] });
      message.success("✓");
      navigate("/payments");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  if (isLoading || !payment) return null;

  const allocColumns = [
    {
      title: payment.direction === "in" ? t("payment.alloc_order") : t("payment.alloc_purchase"),
      key: "doc",
      render: (_: any, row: any) => {
        if (row.order_id) {
          return (
            <Button type="link" size="small" onClick={() => navigate(`/orders/${row.order_id}`)}>
              {row.order_number}
            </Button>
          );
        }
        return (
          <Button type="link" size="small" onClick={() => navigate(`/purchases/${row.purchase_id}`)}>
            {row.purchase_number}
          </Button>
        );
      },
    },
    {
      title: `${t("payment.alloc_amount")} CNY`,
      dataIndex: "amount_cny",
      key: "amount",
      align: "right" as const,
      render: (v: number) => fmtCny(v),
    },
    {
      title: t("payment.notes"),
      dataIndex: "notes",
      key: "notes",
      render: (v: string) => v || "—",
    },
  ];

  return (
    <div style={{ maxWidth: 900 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/payments")}>
              {t("common.back")}
            </Button>
            <Title level={4} style={{ margin: 0 }}>
              {payment.direction === "in" ? t("payment.incoming") : t("payment.outgoing")} —{" "}
              {payment.counterparty_name}
            </Title>
          </Space>
        </Col>
        <Col>
          <Popconfirm
            title={t("payment.delete_confirm")}
            onConfirm={() => deleteMutation.mutate()}
            okText={t("common.yes")}
            cancelText={t("common.no")}
          >
            <Button danger icon={<DeleteOutlined />} loading={deleteMutation.isPending}>
              {t("common.delete")}
            </Button>
          </Popconfirm>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label={t("payment.direction")}>
            <Tag color={payment.direction === "in" ? "green" : "red"}>
              {payment.direction === "in" ? t("payment.incoming") : t("payment.outgoing")}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label={t("payment.date")}>{payment.payment_date}</Descriptions.Item>
          <Descriptions.Item label={t("payment.counterparty")}>{payment.counterparty_name}</Descriptions.Item>
          <Descriptions.Item label={t("payment.currency")}>{payment.currency}</Descriptions.Item>
          <Descriptions.Item label={t("payment.amount")}>
            {fmtCny(payment.amount)} {payment.currency}
          </Descriptions.Item>
          <Descriptions.Item label={t("payment.rate_to_cny")}>
            {Number(payment.rate_to_cny).toFixed(8)}
          </Descriptions.Item>
          <Descriptions.Item label={`${t("payment.amount_cny")} (CNY)`}>
            <Text strong>{fmtCny(payment.amount_cny)}</Text>
          </Descriptions.Item>
          {payment.network_fee != null && (
            <Descriptions.Item label={t("payment.network_fee")}>
              {fmtCny(payment.network_fee)} USDT
            </Descriptions.Item>
          )}
          {payment.notes && (
            <Descriptions.Item label={t("payment.notes")} span={2}>{payment.notes}</Descriptions.Item>
          )}
          <Descriptions.Item label={t("common.created_by")}>{payment.created_by_name}</Descriptions.Item>
          <Descriptions.Item label={t("common.created_at")}>
            {new Date(payment.created_at).toLocaleString("ru-RU")}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title={t("payment.allocations")} style={{ marginBottom: 16 }}>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Statistic title={`${t("payment.amount_cny")} CNY`} value={fmtCny(payment.amount_cny)} />
          </Col>
          <Col span={8}>
            <Statistic
              title={t("payment.allocated")}
              value={fmtCny(payment.allocated_cny)}
              valueStyle={{ color: "#389e0d" }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title={t("payment.unallocated")}
              value={fmtCny(payment.unallocated_cny)}
              valueStyle={{ color: Number(payment.unallocated_cny) > 0 ? "#faad14" : undefined }}
            />
          </Col>
        </Row>

        {payment.allocations.length > 0 ? (
          <Table
            dataSource={payment.allocations}
            rowKey="id"
            size="small"
            pagination={false}
            columns={allocColumns}
            summary={() => (
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} align="right">
                  <Text strong>{t("payment.allocated")}</Text>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={1} align="right">
                  <Text strong>{fmtCny(payment.allocated_cny)} CNY</Text>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={2} />
              </Table.Summary.Row>
            )}
          />
        ) : (
          <Text type="secondary">
            {t("payment.unallocated")} — платёж сохранён как аванс
          </Text>
        )}
      </Card>
    </div>
  );
}
