import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Descriptions, Button, Tag, Typography, Space, Popconfirm,
  Row, Col, Card, Modal, Form, Input, DatePicker, message, Skeleton,
} from "antd";
import {
  EditOutlined, DeleteOutlined, CheckOutlined,
  CloseOutlined, DollarOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import {
  getExpense, deleteExpense,
  approveReimbursement, rejectReimbursement, markReimbursementPaid,
} from "../api/expenses";
import type { User } from "../types";

const { Title, Text } = Typography;

const REIMBURSE_COLORS: Record<string, string> = {
  pending: "gold",
  approved: "blue",
  paid: "green",
  rejected: "red",
};

const fmtCny = (v: number | string) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props { user: User }

export default function ExpenseDetailPage({ user }: Props) {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const isAccountant = user.roles?.some(r => ["accountant", "admin"].includes(r));

  const [rejectOpen, setRejectOpen] = useState(false);
  const [paidOpen, setPaidOpen] = useState(false);
  const [rejectForm] = Form.useForm();
  const [paidForm] = Form.useForm();

  const { data: expense, isLoading } = useQuery({
    queryKey: ["expense", id],
    queryFn: () => getExpense(id!).then(r => r.data),
    enabled: !!id,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["expense", id] });
    qc.invalidateQueries({ queryKey: ["expenses"] });
  };

  const deleteMutation = useMutation({
    mutationFn: () => deleteExpense(id!),
    onSuccess: () => { message.success("✓"); navigate("/expenses"); },
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
    mutationFn: (paid_date: string) => markReimbursementPaid(id!, paid_date),
    onSuccess: () => { message.success("✓"); invalidate(); setPaidOpen(false); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  if (isLoading) return <Skeleton active />;
  if (!expense) return null;

  const isOwner = expense.created_by === user.id;
  const canEdit = isAccountant || (isOwner && expense.reimburse_status !== "paid");
  const canDelete = isAccountant || (isOwner && expense.reimburse_status !== "paid");

  return (
    <div style={{ maxWidth: 800 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("expense.detail_title")}</Title>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate("/expenses")}>{t("common.back")}</Button>
            {canEdit && (
              <Button icon={<EditOutlined />} onClick={() => navigate(`/expenses/${id}/edit`)}>
                {t("common.edit")}
              </Button>
            )}
            {canDelete && (
              <Popconfirm
                title={t("expense.delete_confirm")}
                onConfirm={() => deleteMutation.mutate()}
                okText={t("common.yes")}
                cancelText={t("common.no")}
              >
                <Button icon={<DeleteOutlined />} danger>
                  {t("common.delete")}
                </Button>
              </Popconfirm>
            )}
          </Space>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small" bordered>
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
            {fmtCny(expense.amount_cny)}
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
          {expense.receipt_url && (
            <Descriptions.Item label={t("expense.receipt_url")} span={2}>
              <a href={expense.receipt_url} target="_blank" rel="noreferrer">{expense.receipt_url}</a>
            </Descriptions.Item>
          )}
          <Descriptions.Item label={t("common.created_by")}>{expense.created_by_name}</Descriptions.Item>
          <Descriptions.Item label={t("common.created_at")}>
            {new Date(expense.created_at).toLocaleString("ru-RU")}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {expense.is_reimbursement && (
        <Card title={t("expense.reimbursement_section")}>
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label={t("expense.reimburse_to")}>
              {expense.reimburse_to_name ?? t("expense.reimburse_self")}
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

          {isAccountant && (
            <Space style={{ marginTop: 16 }}>
              {expense.reimburse_status === "pending" && (
                <>
                  <Popconfirm
                    title={t("expense.approve_confirm")}
                    onConfirm={() => approveMutation.mutate()}
                    okText={t("common.yes")}
                    cancelText={t("common.no")}
                  >
                    <Button
                      type="primary"
                      icon={<CheckOutlined />}
                      loading={approveMutation.isPending}
                    >
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
      )}

      {/* Reject modal */}
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

      {/* Mark paid modal */}
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
          onFinish={v => paidMutation.mutate(v.paid_date.format("YYYY-MM-DD"))}
        >
          <Form.Item name="paid_date" label={t("expense.reimburse_paid_date")} rules={[{ required: true }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
