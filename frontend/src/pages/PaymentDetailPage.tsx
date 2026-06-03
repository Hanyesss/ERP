import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Button, Card, Col, Descriptions, Divider, Form, Input, InputNumber,
  Modal, Popconfirm, Row, Select, DatePicker, Space, Statistic,
  Table, Tag, Typography, message,
} from "antd";
import { DeleteOutlined, ArrowLeftOutlined, EditOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import { getPayment, deletePayment, updatePayment } from "../api/payments";

const { Title, Text } = Typography;

const fmtCny = (v: number | string | null | undefined) =>
  v != null ? Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2 }) : "—";

export default function PaymentDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const backUrl = searchParams.get("back") || "/payments";
  const qc = useQueryClient();

  const [editOpen, setEditOpen] = useState(false);
  const [editForm] = Form.useForm();
  const [deleteModal, setDeleteModal] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");

  const { data: payment, isLoading } = useQuery({
    queryKey: ["payment", id],
    queryFn: () => getPayment(id!).then(r => r.data),
    enabled: !!id,
  });

  const updateMutation = useMutation({
    mutationFn: (data: any) => updatePayment(id!, data),
    onSuccess: () => {
      message.success("✓");
      qc.invalidateQueries({ queryKey: ["payment", id] });
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      setEditOpen(false);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (reason: string) => deletePayment({ id: id!, reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["purchases"] });
      message.success("✓");
      navigate(backUrl);
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
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(backUrl)}>
              {t("common.back")}
            </Button>
            <Title level={4} style={{ margin: 0 }}>
              {payment.direction === "in" ? t("payment.incoming") : t("payment.outgoing")} —{" "}
              {payment.counterparty_name}
            </Title>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<EditOutlined />}
              onClick={() => {
                editForm.setFieldsValue({
                  payment_date: dayjs(payment.payment_date),
                  currency: payment.currency,
                  amount: Number(payment.amount),
                  rate_to_cny: Number(payment.rate_to_cny),
                  network_fee: payment.network_fee != null ? Number(payment.network_fee) : undefined,
                  notes: payment.notes,
                });
                setEditOpen(true);
              }}
            >
              {t("common.edit")}
            </Button>
            <>
              <Modal open={deleteModal} title={t("payment.delete_modal_title")}
                onOk={() => { if (deleteReason.trim()) deleteMutation.mutate(deleteReason.trim()); }}
                onCancel={() => setDeleteModal(false)}
                okText={t("common.delete")} cancelText={t("common.cancel")}
                okButtonProps={{ danger: true, disabled: !deleteReason.trim(), loading: deleteMutation.isPending }}
                destroyOnClose>
                <p style={{ marginBottom: 8 }}>{t("payment.delete_reason_label")}:</p>
                <Input.TextArea rows={3} value={deleteReason} onChange={e => setDeleteReason(e.target.value)} autoFocus />
              </Modal>
              <Button danger icon={<DeleteOutlined />} onClick={() => { setDeleteReason(""); setDeleteModal(true); }}>
                {t("common.delete")}
              </Button>
            </>
          </Space>
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
          <Table scroll={{ x: "max-content" }}
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

      <Modal
        open={editOpen}
        title={t("common.edit")}
        onCancel={() => setEditOpen(false)}
        onOk={() => editForm.submit()}
        confirmLoading={updateMutation.isPending}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        destroyOnClose
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(v) => updateMutation.mutate({
            payment_date: v.payment_date.format("YYYY-MM-DD"),
            currency: v.currency,
            amount: v.amount,
            rate_to_cny: v.rate_to_cny,
            network_fee: v.network_fee ?? null,
            notes: v.notes ?? null,
          })}
        >
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="payment_date" label={t("payment.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="currency" label={t("payment.currency")} rules={[{ required: true }]}>
                <Select options={["CNY","RUB","USDT","USD"].map(c => ({ value: c, label: c }))} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="amount" label={t("payment.amount")} rules={[{ required: true }]}>
                <InputNumber min={0} step={0.01} precision={2} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="rate_to_cny" label={t("payment.rate_to_cny")} rules={[{ required: true }]}>
                <InputNumber min={0} step={0.0001} precision={8} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          {payment.currency === "USDT" && (
            <Form.Item name="network_fee" label={t("payment.network_fee")}>
              <InputNumber min={0} step={0.01} precision={2} style={{ width: "100%" }} />
            </Form.Item>
          )}
          <Form.Item name="notes" label={t("payment.notes")}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
