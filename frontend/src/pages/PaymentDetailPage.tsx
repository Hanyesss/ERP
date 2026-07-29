import { useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Button, Card, Col, Descriptions, Divider, Form, Input, InputNumber,
  Modal, Popconfirm, Row, Select, DatePicker, Space, Statistic,
  Table, Tag, Typography, Upload, message, Alert,
} from "antd";
import { DeleteOutlined, ArrowLeftOutlined, EditOutlined, UploadOutlined, FileOutlined } from "@ant-design/icons";
import type { UploadRequestOption } from "rc-upload/lib/interface";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import { getPayment, deletePayment, updatePayment, uploadPaymentReceipt, deletePaymentReceipt, deletePaymentReceiptFile, requestPaymentChange, approvePaymentChange, rejectPaymentChange } from "../api/payments";
import { getCashRegisters } from "../api/cashRegisters";
import { getPaymentPlans } from "../api/paymentPlans";
import PlanSettleModal from "../components/payments/PlanSettleModal";
import apiClient from "../api/client";
import { compressImage } from "../utils/compressImage";
import type { User } from "../types";

const { Title, Text } = Typography;

const fmtCny = (v: number | string | null | undefined) =>
  v != null ? Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2 }) : "—";

interface Props { user?: User }

export default function PaymentDetailPage({ user }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const backUrl = searchParams.get("back") || "/payments";
  const qc = useQueryClient();

  const isAccountant = user?.roles?.some(r => ["accountant", "admin"].includes(r)) ?? false;

  const [editOpen, setEditOpen] = useState(false);
  const [editForm] = Form.useForm();
  const [deleteModal, setDeleteModal] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");
  const [changeRequestOpen, setChangeRequestOpen] = useState(false);
  const [changeRequestForm] = Form.useForm();

  const { data: payment, isLoading } = useQuery({
    queryKey: ["payment", id],
    queryFn: () => getPayment(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: cashRegisters = [] } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then(r => r.data),
    enabled: isAccountant,
  });

  // План (остаток) по связанному заказу/закупке — для кнопки «Оплатить остаток»
  const linkedOrderId = (payment?.allocations as any[])?.find(a => a.order_id)?.order_id;
  const linkedPurchaseId = (payment?.allocations as any[])?.find(a => a.purchase_id)?.purchase_id;
  const { data: linkedPlanData } = useQuery({
    queryKey: ["payment-plans", "doc", linkedOrderId || linkedPurchaseId],
    queryFn: () => getPaymentPlans(
      linkedOrderId ? { order_id: linkedOrderId } : { purchase_id: linkedPurchaseId! }
    ).then(r => r.data),
    enabled: !!(linkedOrderId || linkedPurchaseId),
  });
  const linkedPlan = linkedPlanData?.items?.[0] ?? null;
  const [settleOpen, setSettleOpen] = useState(false);

  // Кросс-валюта в форме редактирования
  const CURRENCY_RANK: Record<string, number> = { USD: 3, USDT: 2, CNY: 1, RUB: 0 };
  const edCurrency: string = Form.useWatch("currency", editForm) || "CNY";
  const edAmount: number = Form.useWatch("amount", editForm) || 0;
  const edRate: number = Form.useWatch("rate_to_cny", editForm) || 1;
  const edRegId: string = Form.useWatch("cash_register_id", editForm);
  const edCashRate: number = Form.useWatch("cash_rate", editForm) || 0;
  const edReg = (cashRegisters as any[]).find(r => r.id === edRegId);
  const edRegCur: string = edReg?.currency ?? "CNY";
  const edNeedRate = !!edRegId && edCurrency !== edRegCur && edRegCur !== "CNY";
  const edLarger = (CURRENCY_RANK[edCurrency] ?? 1) >= (CURRENCY_RANK[edRegCur] ?? 1) ? edCurrency : edRegCur;
  const edSmaller = (CURRENCY_RANK[edCurrency] ?? 1) >= (CURRENCY_RANK[edRegCur] ?? 1) ? edRegCur : edCurrency;

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

  const receiptMutation = useMutation({
    mutationFn: (file: File) => uploadPaymentReceipt(id!, file),
    onSuccess: () => {
      message.success(t("payment.receipt_uploaded"));
      qc.invalidateQueries({ queryKey: ["payment", id] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const deleteReceiptMutation = useMutation({
    mutationFn: () => deletePaymentReceipt(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payment", id] }),
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const deleteReceiptFileMutation = useMutation({
    mutationFn: (filename: string) => deletePaymentReceiptFile(id!, filename),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payment", id] }),
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["payment", id] });
    qc.invalidateQueries({ queryKey: ["payments"] });
    qc.invalidateQueries({ queryKey: ["orders"] });
  };

  const approveChangeMutation = useMutation({
    mutationFn: () => approvePaymentChange(id!),
    onSuccess: () => { message.success(t("payment.change_approved")); invalidate(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const rejectChangeMutation = useMutation({
    mutationFn: () => rejectPaymentChange(id!),
    onSuccess: () => { message.success(t("payment.change_rejected")); invalidate(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const requestChangeMutation = useMutation({
    mutationFn: (data: any) => requestPaymentChange(id!, data),
    onSuccess: () => { message.success(t("payment.change_request_sent")); setChangeRequestOpen(false); invalidate(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleReceiptUpload = async ({ file }: UploadRequestOption) => {
    const compressed = await compressImage(file as File);
    receiptMutation.mutate(compressed);
  };

  if (isLoading || !payment) return null;

  const pendingChange = payment.pending_change ? (() => { try { return JSON.parse(payment.pending_change!); } catch { return null; } })() : null;

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
            {isAccountant && (
              <Button
                icon={<EditOutlined />}
                onClick={() => {
                  editForm.setFieldsValue({
                    payment_date: dayjs(payment.payment_date),
                    currency: payment.currency,
                    amount: Number(payment.amount),
                    rate_to_cny: Number(payment.rate_to_cny),
                    cash_register_id: (payment as any).cash_register_id ?? undefined,
                    network_fee: payment.network_fee != null ? Number(payment.network_fee) : undefined,
                    notes: payment.notes,
                  });
                  setEditOpen(true);
                }}
              >
                {t("common.edit")}
              </Button>
            )}
            {!isAccountant && !pendingChange && (
              <Button onClick={() => { changeRequestForm.resetFields(); setChangeRequestOpen(true); }}>
                {t("payment.request_change")}
              </Button>
            )}
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
          {(payment as any).payment_source === "trontok" && (
            <Descriptions.Item label="Источник" span={2}>
              <Tag color="geekblue">TronTok USDT</Tag>
              {(payment as any).external_tx_id && (
                <span style={{ marginLeft: 8, fontFamily: "monospace", fontSize: 12, color: "#888" }}>
                  ref: {(payment as any).external_tx_id}
                </span>
              )}
            </Descriptions.Item>
          )}
          <Descriptions.Item label={t("common.created_by")}>{payment.created_by_name}</Descriptions.Item>
          <Descriptions.Item label={t("common.created_at")}>
            {new Date(payment.created_at).toLocaleString("ru-RU")}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Pending amount change */}
      {pendingChange && (
        <Alert
          type={isAccountant ? "warning" : "info"}
          showIcon
          style={{ marginBottom: 16 }}
          message={t("payment.pending_change_title")}
          description={
            <Space direction="vertical" size={4}>
              <span>{t("payment.new_amount")}: <strong>{pendingChange.amount} {pendingChange.currency}</strong>{pendingChange.rate_to_cny ? ` (курс: ${pendingChange.rate_to_cny})` : ""}</span>
              {pendingChange.reason && <span>{t("payment.change_reason")}: {pendingChange.reason}</span>}
              <span style={{ color: "#888", fontSize: 12 }}>{pendingChange.requested_by_name} · {new Date(pendingChange.requested_at).toLocaleString("ru-RU")}</span>
              {isAccountant && (
                <Space style={{ marginTop: 8 }}>
                  <Button type="primary" size="small" loading={approveChangeMutation.isPending} onClick={() => approveChangeMutation.mutate()}>{t("payment.approve_change")}</Button>
                  <Button danger size="small" loading={rejectChangeMutation.isPending} onClick={() => rejectChangeMutation.mutate()}>{t("payment.reject_change")}</Button>
                </Space>
              )}
              {!isAccountant && <Tag color="gold">{t("payment.pending_change_waiting")}</Tag>}
            </Space>
          }
        />
      )}

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

      {linkedPlan && Number(linkedPlan.remaining_cny) > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`${t("plan.doc_remaining")}: ${fmtCny(linkedPlan.remaining_cny)} CNY (${linkedPlan.doc_number || ""})`}
          action={
            isAccountant && (
              <Button size="small" type="primary" onClick={() => setSettleOpen(true)}>
                {t("plan.pay_remaining")}
              </Button>
            )
          }
        />
      )}
      <PlanSettleModal plan={settleOpen ? linkedPlan : null} open={settleOpen} onClose={() => setSettleOpen(false)} />

      <Card title={t("payment.receipt")} style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Space wrap>
            {(payment.file_urls?.length ?? 0) < 10 && (
              <Upload customRequest={handleReceiptUpload} showUploadList={false} accept=".jpg,.jpeg,.png,.webp,.pdf">
                <Button icon={<UploadOutlined />} loading={receiptMutation.isPending}>
                  {t("payment.receipt_upload")}
                </Button>
              </Upload>
            )}
            <span style={{ color: "#999", fontSize: 12 }}>
              {payment.file_urls?.length ?? 0} / 10
            </span>
          </Space>

          {(payment.file_urls ?? []).length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
              {(payment.file_urls ?? []).map((fileUrl) => {
                const url = `${apiClient.defaults.baseURL}/files/${fileUrl}`;
                const filename = fileUrl.split("/").pop() || fileUrl;
                const isPdf = fileUrl.toLowerCase().endsWith(".pdf");
                return (
                  <div key={fileUrl} style={{ position: "relative", border: "1px solid #f0f0f0", borderRadius: 6, padding: 4 }}>
                    {isPdf ? (
                      <a href={url} target="_blank" rel="noreferrer" style={{ display: "flex", alignItems: "center", gap: 4, padding: "8px 12px" }}>
                        <FileOutlined style={{ fontSize: 28, color: "#ff4d4f" }} />
                        <span style={{ fontSize: 12, maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {filename}
                        </span>
                      </a>
                    ) : (
                      <a href={url} target="_blank" rel="noreferrer">
                        <img
                          src={url}
                          alt="receipt"
                          style={{ width: 120, height: 120, objectFit: "cover", borderRadius: 4, cursor: "zoom-in", display: "block" }}
                        />
                      </a>
                    )}
                    <Popconfirm
                      title={t("payment.receipt_delete") + "?"}
                      onConfirm={() => deleteReceiptFileMutation.mutate(filename)}
                      okText={t("common.yes")}
                      cancelText={t("common.no")}
                    >
                      <Button
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        loading={deleteReceiptFileMutation.isPending}
                        style={{ position: "absolute", top: 2, right: 2, minWidth: 24, padding: "0 4px" }}
                      />
                    </Popconfirm>
                  </div>
                );
              })}
            </div>
          )}
        </Space>
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
          onFinish={(v) => {
            if (edNeedRate && (!v.cash_rate || v.cash_rate <= 0)) {
              message.error(t("expense.cross_currency_error")); return;
            }
            updateMutation.mutate({
              payment_date: v.payment_date.format("YYYY-MM-DD"),
              currency: v.currency,
              amount: v.amount,
              rate_to_cny: v.rate_to_cny,
              cash_register_id: v.cash_register_id ?? null,
              cash_rate: edNeedRate ? v.cash_rate : undefined,
              network_fee: v.network_fee ?? null,
              notes: v.notes ?? null,
            });
          }}
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
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item label={`${t("payment.amount_cny")} (CNY)`}>
                <InputNumber disabled value={Number((edAmount * edRate).toFixed(2))} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="cash_register_id" label={t("expense.cash_register")}>
                <Select allowClear
                  placeholder={t("expense.select_cash_register")}
                  options={(cashRegisters as any[]).filter(r => r.is_active).map(r => ({
                    value: r.id, label: `${r.name} (${r.currency})`,
                  }))} />
              </Form.Item>
            </Col>
          </Row>
          {edNeedRate && (
            <>
              <Form.Item name="cash_rate"
                label={t("expense.cash_rate_label", { larger: edLarger, smaller: edSmaller })}
                rules={[{ required: true, message: t("expense.cash_rate_hint") }]}>
                <InputNumber min={0.000001} step={0.01} precision={6} style={{ width: "100%" }}
                  placeholder={`1 ${edLarger} = ? ${edSmaller}`} />
              </Form.Item>
              {edCashRate > 0 && (
                <Alert type="info" showIcon style={{ marginBottom: 8 }}
                  message={`${t("expense.cash_deduction")}: ${((CURRENCY_RANK[edCurrency] ?? 1) > (CURRENCY_RANK[edRegCur] ?? 1) ? edAmount * edCashRate : edAmount / edCashRate).toFixed(6)} ${edRegCur}`} />
              )}
            </>
          )}
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

      {/* Change request modal for non-accountants */}
      <Modal
        open={changeRequestOpen}
        title={t("payment.request_change")}
        onCancel={() => setChangeRequestOpen(false)}
        onOk={() => changeRequestForm.submit()}
        confirmLoading={requestChangeMutation.isPending}
        okText={t("common.send")}
        cancelText={t("common.cancel")}
        destroyOnClose
      >
        <Form form={changeRequestForm} layout="vertical" onFinish={v => requestChangeMutation.mutate({ amount: v.amount, rate_to_cny: v.rate_to_cny, reason: v.reason })}>
          <Form.Item name="amount" label={t("payment.amount")} rules={[{ required: true }]} initialValue={Number(payment?.amount)}>
            <InputNumber style={{ width: "100%" }} min={0} step={0.01} precision={2} />
          </Form.Item>
          <Form.Item name="rate_to_cny" label={t("payment.rate_to_cny")} initialValue={Number(payment?.rate_to_cny)}>
            <InputNumber style={{ width: "100%" }} min={0} step={0.0001} precision={8} />
          </Form.Item>
          <Form.Item name="reason" label={t("payment.change_reason")}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
