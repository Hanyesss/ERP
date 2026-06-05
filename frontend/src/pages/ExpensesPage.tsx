import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button, Tag, Row, Col, Input, Select, DatePicker,
  Typography, Space, Statistic, message, Modal,
} from "antd";
import TopScrollTable from "../components/common/TopScrollTable";
import { PlusOutlined, EyeOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import { getExpenses, deleteExpense } from "../api/expenses";
import type { ExpenseListItem } from "../types/expense";
import type { User } from "../types";

const { Title } = Typography;
const { RangePicker } = DatePicker;

const fmtCny = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const REIMBURSE_COLORS: Record<string, string> = {
  pending: "gold",
  approved: "blue",
  paid: "green",
  rejected: "red",
};

interface Props { user: User }

export default function ExpensesPage({ user }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const isAccountant = user.roles?.some(r => ["accountant", "admin"].includes(r));

  const [deleteModal, setDeleteModal] = useState<{ open: boolean; expenseId: string | null }>({ open: false, expenseId: null });
  const [deleteReason, setDeleteReason] = useState("");

  const [search, setSearch] = useState("");
  const [linkType, setLinkType] = useState<string | undefined>();
  const [currency, setCurrency] = useState<string | undefined>();
  const [isReimbursement, setIsReimbursement] = useState<boolean | undefined>();
  const [reimburseStatus, setReimburseStatus] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [page, setPage] = useState(1);

  const params = {
    search: search || undefined,
    link_type: linkType,
    currency,
    is_reimbursement: isReimbursement,
    reimburse_status: reimburseStatus,
    date_from: dateRange?.[0],
    date_to: dateRange?.[1],
    page,
    page_size: 20,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["expenses", params],
    queryFn: () => getExpenses(params).then(r => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteExpense,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expenses"] });
      message.success("✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const columns: ColumnsType<ExpenseListItem> = [
    {
      title: t("expense.date"),
      dataIndex: "expense_date",
      key: "date",
      width: 110,
    },
    {
      title: t("expense.category"),
      key: "category",
      render: (_, row) => row.category_name_cn
        ? `${row.category_name} / ${row.category_name_cn}`
        : row.category_name,
    },
    {
      title: t("expense.link_type"),
      key: "link",
      width: 120,
      render: (_, row) => {
        if (row.link_type === "order" && row.order_number) {
          return <Tag color="blue">{t("expense.link_order")}: {row.order_number}</Tag>;
        }
        if (row.link_type === "client" && row.client_name) {
          return <Tag color="purple">{t("expense.link_client")}: {row.client_name}</Tag>;
        }
        return <Tag color="default">{t("expense.link_none")}</Tag>;
      },
    },
    {
      title: t("expense.amount"),
      key: "amount",
      align: "right",
      width: 130,
      render: (_, row) => `${fmtCny(row.amount)} ${row.currency}`,
    },
    {
      title: `${t("expense.amount_cny")} (CNY)`,
      dataIndex: "amount_cny",
      key: "amount_cny",
      align: "right",
      width: 120,
      render: v => fmtCny(v),
    },
    {
      title: t("expense.description"),
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: t("expense.cash_register"),
      key: "cash_register",
      width: 130,
      render: (_: any, row: ExpenseListItem) =>
        row.cash_register_name
          ? <Tag color="blue" style={{ fontSize: 11 }}>{row.cash_register_name}</Tag>
          : null,
    },
    {
      title: t("expense.reimbursement"),
      key: "reimburse",
      width: 140,
      render: (_, row) => {
        if (!row.is_reimbursement) return null;
        const color = REIMBURSE_COLORS[row.reimburse_status || "pending"];
        return (
          <Tag color={color}>
            {t(`expense.reimburse_${row.reimburse_status || "pending"}`)}
          </Tag>
        );
      },
    },
    ...(isAccountant ? [{
      title: t("common.created_by"),
      dataIndex: "created_by_name",
      key: "creator",
      width: 120,
    }] : []),
    {
      title: t("common.actions"),
      key: "actions",
      width: 90,
      render: (_: any, row: ExpenseListItem) => (
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => navigate(`/expenses/${row.id}`)} />
          <Button
            icon={<DeleteOutlined />}
            size="small"
            danger
            onClick={() => { setDeleteReason(""); setDeleteModal({ open: true, expenseId: row.id }); }}
          />
        </Space>
      ),
    },
  ];

  const total = data?.total_cny ?? 0;
  const orderTotal = data?.total_order_cny ?? 0;
  const clientTotal = data?.total_client_cny ?? 0;
  const noneTotal = data?.total_none_cny ?? 0;

  const handleDeleteConfirm = () => {
    if (!deleteModal.expenseId || !deleteReason.trim()) return;
    deleteMutation.mutate({ id: deleteModal.expenseId, reason: deleteReason.trim() });
    setDeleteModal({ open: false, expenseId: null });
  };

  return (
    <div>
      <Modal
        open={deleteModal.open}
        title={t("expense.delete_modal_title")}
        onOk={handleDeleteConfirm}
        onCancel={() => setDeleteModal({ open: false, expenseId: null })}
        okText={t("common.delete")}
        cancelText={t("common.cancel")}
        okButtonProps={{ danger: true, disabled: !deleteReason.trim(), loading: deleteMutation.isPending }}
        destroyOnClose
      >
        <p style={{ marginBottom: 8 }}>{t("expense.delete_reason_label")}:</p>
        <Input.TextArea
          rows={3}
          placeholder={t("expense.delete_reason_placeholder")}
          value={deleteReason}
          onChange={e => setDeleteReason(e.target.value)}
          autoFocus
        />
      </Modal>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("expense.title")}</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/expenses/new")}>
            {t("expense.create_new")}
          </Button>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Statistic title={t("expense.total_cny")} value={fmtCny(total)} valueStyle={{ color: "#cf1322" }} />
        </Col>
        <Col span={6}>
          <Statistic title={t("expense.total_order_cny")} value={fmtCny(orderTotal)} />
        </Col>
        <Col span={6}>
          <Statistic title={t("expense.total_client_cny")} value={fmtCny(clientTotal)} />
        </Col>
        <Col span={6}>
          <Statistic title={t("expense.total_none_cny")} value={fmtCny(noneTotal)} />
        </Col>
      </Row>

      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col>
          <Input.Search
            placeholder={t("expense.search_placeholder")}
            allowClear
            style={{ width: 200 }}
            onSearch={v => { setSearch(v); setPage(1); }}
            onChange={e => { if (!e.target.value) { setSearch(""); setPage(1); } }}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("expense.filter_link_type")}
            style={{ width: 160 }}
            options={[
              { value: "order", label: t("expense.link_order") },
              { value: "client", label: t("expense.link_client") },
              { value: "none", label: t("expense.link_none") },
            ]}
            onChange={v => { setLinkType(v); setPage(1); }}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("expense.currency")}
            style={{ width: 100 }}
            options={["CNY", "RUB", "USDT", "USD"].map(c => ({ value: c, label: c }))}
            onChange={v => { setCurrency(v); setPage(1); }}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("expense.filter_reimbursement")}
            style={{ width: 180 }}
            options={[
              { value: "true", label: t("expense.only_reimbursements") },
              { value: "false", label: t("expense.only_direct") },
            ]}
            onChange={v => { setIsReimbursement(v === undefined ? undefined : v === "true"); setPage(1); }}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("expense.filter_reimburse_status")}
            style={{ width: 160 }}
            options={["pending", "approved", "paid", "rejected"].map(s => ({
              value: s,
              label: t(`expense.reimburse_${s}`),
            }))}
            onChange={v => { setReimburseStatus(v); setPage(1); }}
          />
        </Col>
        <Col>
          <RangePicker
            style={{ width: 240 }}
            onChange={(_, strs) => {
              setDateRange(strs[0] && strs[1] ? [strs[0], strs[1]] : null);
              setPage(1);
            }}
          />
        </Col>
      </Row>

      <TopScrollTable
        scroll={{ x: "max-content" }}
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{
          current: page,
          total: data?.total ?? 0,
          pageSize: 20,
          onChange: setPage,
          showTotal: total => `${total}`,
        }}
      />
    </div>
  );
}
