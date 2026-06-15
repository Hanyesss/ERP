import { useRef, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import {
  Descriptions, Button, Tag, Typography, Space, Popconfirm,
  Row, Col, Card, Modal, Form, Input, DatePicker, Select, message,
  Skeleton, Timeline, Upload, Tabs,
} from "antd";
import {
  EditOutlined, DeleteOutlined, CheckOutlined,
  CloseOutlined, DollarOutlined, UploadOutlined, FileOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import type { UploadRequestOption } from "rc-upload/lib/interface";
import {
  getExpense, deleteExpense,
  approveReimbursement, rejectReimbursement, markReimbursementPaid,
  uploadReceipt, uploadQrPhoto, deleteQrPhoto, getExpenseHistory, getFileUrl,
} from "../api/expenses";
import { getCashRegisters } from "../api/cashRegisters";
import type { User } from "../types";

const { Title, Text } = Typography;

const REIMBURSE_COLORS: Record<string, string> = {
  pending: "gold",
  approved: "blue",
  paid: "green",
  rejected: "red",
};

const ACTION_LABELS: Record<string, string> = {
  create: "Создано",
  update: "Изменено",
  delete: "Удалено",
};

const fmtCny = (v: number | string) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props { user: User }

export default function ExpenseDetailPage({ user }: Props) {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const backUrl = searchParams.get("back") || "/expenses";
  const qc = useQueryClient();

  const isAccountant = user.roles?.some(r => ["accountant", "admin"].includes(r));
  const [deleteModal, setDeleteModal] = useState(false);
  const [deleteReason, setDeleteReason] = useState("");

  const [rejectOpen, setRejectOpen] = useState(false);
  const [paidOpen, setPaidOpen] = useState(false);
  const [rejectForm] = Form.useForm();
  const [paidForm] = Form.useForm();
  const uploadRef = useRef<HTMLInputElement>(null);

  const { data: expense, isLoading } = useQuery({
    queryKey: ["expense", id],
    queryFn: () => getExpense(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: history } = useQuery({
    queryKey: ["expense-history", id],
    queryFn: () => getExpenseHistory(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: cashRegisters = [] } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then(r => r.data),
    enabled: isAccountant,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["expense", id] });
    qc.invalidateQueries({ queryKey: ["expenses"] });
    qc.invalidateQueries({ queryKey: ["expense-history", id] });
  };

  const deleteMutation = useMutation({
    mutationFn: (reason: string) => deleteExpense({ id: id!, reason }),
    onSuccess: () => { message.success("✓"); navigate(backUrl); setDeleteModal(false); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const approveMutation = useMutation({
    mutationFn: () => approveReimbursement(id!),
    onSuccess: () => { message.success("✓"); invalidate(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const rejectMutation = useMutation({
    mutationFn: (reason: string) => rejectReimbursement(id!, reason),
    onSuccess: () => { message.success("✓"); invalidate(); setRejectOpen(false); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const paidMutation = useMutation({
    mutationFn: (data: { paid_date: string; cash_register_id?: string }) =>
      markReimbursementPaid(id!, data),
    onSuccess: () => { message.success("✓"); invalidate(); setPaidOpen(false); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const receiptMutation = useMutation({
    mutationFn: (file: File) => uploadReceipt(id!, file),
    onSuccess: () => { message.success(t("expense.receipt_uploaded")); invalidate(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const qrMutation = useMutation({
    mutationFn: (file: File) => uploadQrPhoto(id!, file),
    onSuccess: () => { message.success(t("expense.qr_uploaded")); invalidate(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const deleteQrMutation = useMutation({
    mutationFn: () => deleteQrPhoto(id!),
    onSuccess: () => invalidate(),
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleReceiptUpload = ({ file }: UploadRequestOption) => {
    receiptMutation.mutate(file as File);
  };

  const handleQrUpload = ({ file }: UploadRequestOption) => {
    qrMutation.mutate(file as File);
  };

  if (isLoading) return <Skeleton active />;
  if (!expense) return null;

  const isOwner = expense.created_by === user.id;
  const canEdit = isAccountant || (isOwner && expense.reimburse_status !== "paid");
  const canDelete = isAccountant || (isOwner && expense.reimburse_status !== "paid");

  const tabs = [
    {
      key: "main",
      label: t("expense.tab_main"),
      children: (
        <>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label={t("expense.date")}>{expense.expense_date}</Descriptions.Item>
            <Descriptions.Item label={t("expense.category")}>
              {expense.category_name_cn
                ? `${expense.category_name} / ${expense.category_name_cn}`
                : expense.category_name}
            </Descriptions.Item>
            <Descriptions.Item label={t("expense.amount")}>
              {fmtCny(expense.amount)} {expense.currency}
            </Descriptions.Item>
            <Descriptions.Item label={`${t("expense.amount_cny")} (CNY)`}>
              <strong>{fmtCny(expense.amount_cny)}</strong>
            </Descriptions.Item>
            <Descriptions.Item label={t("expense.rate_to_cny")}>
              {expense.rate_to_cny}
            </Descriptions.Item>
            <Descriptions.Item label={t("expense.link_type")}>
              {expense.link_type === "order" && expense.order_number
                ? <Tag color="blue">{t("expense.link_order")}: {expense.order_number}</Tag>
                : expense.link_type === "client" && expense.client_name
                ? <Tag color="purple">{t("expense.link_client")}: {expense.client_name}</Tag>
                : <Tag>{t("expense.link_none")}</Tag>
              }
            </Descriptions.Item>
            <Descriptions.Item label={t("expense.description")} span={2}>
              {expense.description}
            </Descriptions.Item>
            {expense.cash_register_name && (
              <Descriptions.Item label={t("expense.cash_register")} span={2}>
                <Tag color="blue">{expense.cash_register_name}</Tag>
              </Descriptions.Item>
            )}
            <Descriptions.Item label={t("common.created_by")}>{expense.created_by_name}</Descriptions.Item>
            <Descriptions.Item label={t("common.created_at")}>
              {new Date(expense.created_at).toLocaleString("ru-RU")}
            </Descriptions.Item>
          </Descriptions>

          {/* Receipt */}
          <Card
            size="small"
            title={t("expense.receipt")}
            extra={
              <Upload
                customRequest={handleReceiptUpload}
                showUploadList={false}
                accept=".jpg,.jpeg,.png,.webp,.pdf"
              >
                <Button
                  icon={<UploadOutlined />}
                  size="small"
                  loading={receiptMutation.isPending}
                >
                  {expense.receipt_url ? t("expense.receipt_replace") : t("expense.receipt_upload")}
                </Button>
              </Upload>
            }
          >
            {expense.receipt_url ? (
              <Space>
                <FileOutlined />
                <a href={getFileUrl(expense.receipt_url)} target="_blank" rel="noreferrer">
                  {t("expense.receipt_view")}
                </a>
              </Space>
            ) : (
              <Text type="secondary">{t("expense.receipt_none")}</Text>
            )}
          </Card>
        </>
      ),
    },

    ...(expense.is_reimbursement ? [{
      key: "reimburse",
      label: t("expense.reimbursement_section"),
      children: (
        <Card>
          <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
            <Descriptions.Item label={t("expense.reimburse_to")}>
              {expense.reimburse_to_name ?? expense.created_by_name}
            </Descriptions.Item>
            <Descriptions.Item label={t("expense.reimburse_status")}>
              <Tag color={REIMBURSE_COLORS[expense.reimburse_status || "pending"]}>
                {t(`expense.reimburse_${expense.reimburse_status || "pending"}`)}
              </Tag>
            </Descriptions.Item>
            {expense.reimburse_paid_date && (
              <Descriptions.Item label={t("expense.reimburse_paid_date")}>
                {expense.reimburse_paid_date}
              </Descriptions.Item>
            )}
            {expense.reject_reason && (
              <Descriptions.Item label={t("expense.reject_reason")} span={2}>
                <Text type="danger">{expense.reject_reason}</Text>
              </Descriptions.Item>
            )}
          </Descriptions>

          {/* QR для получения платежа */}
          <Card
            size="small"
            title={t("expense.qr_title")}
            style={{ marginBottom: 16 }}
            extra={
              <Space>
                <Upload customRequest={handleQrUpload} showUploadList={false} accept=".jpg,.jpeg,.png,.webp">
                  <Button icon={<UploadOutlined />} size="small" loading={qrMutation.isPending}>
                    {expense.qr_url ? t("expense.qr_replace") : t("expense.qr_upload")}
                  </Button>
                </Upload>
                {expense.qr_url && (
                  <Popconfirm
                    title={t("expense.qr_delete_confirm")}
                    onConfirm={() => deleteQrMutation.mutate()}
                    okText={t("common.yes")}
                    cancelText={t("common.no")}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} loading={deleteQrMutation.isPending} />
                  </Popconfirm>
                )}
              </Space>
            }
          >
            {expense.qr_url ? (
              <a href={getFileUrl(expense.qr_url)} target="_blank" rel="noreferrer">
                <img
                  src={getFileUrl(expense.qr_url)}
                  alt="QR"
                  style={{ maxWidth: 220, maxHeight: 220, borderRadius: 4, border: "1px solid #f0f0f0" }}
                />
              </a>
            ) : (
              <Text type="secondary">{t("expense.qr_not_uploaded")}</Text>
            )}
          </Card>

          {isAccountant && (
            <Space>
              {expense.reimburse_status === "pending" && (
                <>
                  <Popconfirm
                    title={t("expense.approve_confirm")}
                    onConfirm={() => approveMutation.mutate()}
                    okText={t("common.yes")}
                    cancelText={t("common.no")}
                  >
                    <Button type="primary" icon={<CheckOutlined />} loading={approveMutation.isPending}>
                      {t("expense.approve")}
                    </Button>
                  </Popconfirm>
                  <Button
                    icon={<CloseOutlined />}
                    danger
                    onClick={() => { rejectForm.resetFields(); setRejectOpen(true); }}
                  >
                    {t("expense.reject")}
                  </Button>
                </>
              )}
              {expense.reimburse_status === "approved" && (
                <Button
                  type="primary"
                  icon={<DollarOutlined />}
                  onClick={() => { paidForm.setFieldValue("paid_date", dayjs()); setPaidOpen(true); }}
                >
                  {t("expense.mark_paid")}
                </Button>
              )}
            </Space>
          )}
        </Card>
      ),
    }] : []),

    {
      key: "history",
      label: t("expense.tab_history"),
      children: (
        <Timeline
          items={(history || []).map((h: any) => ({
            children: (
              <div>
                <Text strong>{ACTION_LABELS[h.action] ?? h.action}</Text>
                {" — "}
                <Text type="secondary">
                  {h.user_name} · {new Date(h.created_at).toLocaleString("ru-RU")}
                </Text>
                {h.changes && Object.keys(h.changes).length > 0 && (
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
    <div style={{ maxWidth: 900 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("expense.detail_title")}</Title>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate(backUrl)}>{t("common.back")}</Button>
            {canEdit && (
              <Button icon={<EditOutlined />} onClick={() => navigate(`/expenses/${id}/edit`)}>
                {t("common.edit")}
              </Button>
            )}
            {canDelete && (
              <>
                <Modal open={deleteModal} title={t("expense.delete_modal_title")}
                  onOk={() => { if (deleteReason.trim()) deleteMutation.mutate(deleteReason.trim()); }}
                  onCancel={() => setDeleteModal(false)}
                  okText={t("common.delete")} cancelText={t("common.cancel")}
                  okButtonProps={{ danger: true, disabled: !deleteReason.trim(), loading: deleteMutation.isPending }}
                  destroyOnClose>
                  <p style={{ marginBottom: 8 }}>{t("expense.delete_reason_label")}:</p>
                  <Input.TextArea rows={3} value={deleteReason} onChange={e => setDeleteReason(e.target.value)} autoFocus />
                </Modal>
                <Button icon={<DeleteOutlined />} danger onClick={() => { setDeleteReason(""); setDeleteModal(true); }}>
                  {t("common.delete")}
                </Button>
              </>
            )}
          </Space>
        </Col>
      </Row>

      <Tabs items={tabs} />

      <Modal
        open={rejectOpen}
        title={t("expense.reject")}
        onCancel={() => setRejectOpen(false)}
        onOk={() => rejectForm.submit()}
        confirmLoading={rejectMutation.isPending}
        okText={t("expense.reject")}
        okButtonProps={{ danger: true }}
      >
        <Form form={rejectForm} layout="vertical" onFinish={v => rejectMutation.mutate(v.reject_reason)}>
          <Form.Item name="reject_reason" label={t("expense.reject_reason")} rules={[{ required: true }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={paidOpen}
        title={t("expense.mark_paid")}
        onCancel={() => setPaidOpen(false)}
        onOk={() => paidForm.submit()}
        confirmLoading={paidMutation.isPending}
        okText={t("common.confirm")}
      >
        <Form
          form={paidForm}
          layout="vertical"
          onFinish={v => paidMutation.mutate({
            paid_date: v.paid_date.format("YYYY-MM-DD"),
            cash_register_id: v.cash_register_id || undefined,
          })}
        >
          <Form.Item name="paid_date" label={t("expense.reimburse_paid_date")} rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="cash_register_id" label={t("expense.cash_register")} rules={[{ required: true, message: t("expense.select_cash_register") }]}>
            <Select
              placeholder={t("expense.select_cash_register")}
              options={(cashRegisters as any[]).filter((r: any) => r.is_active).map((r: any) => ({
                value: r.id,
                label: `${r.name} (${r.currency})`,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
