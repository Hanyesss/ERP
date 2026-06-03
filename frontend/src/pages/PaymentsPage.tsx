import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table, Button, Tag, Row, Col, Input, Select, DatePicker,
  Typography, Space, Statistic, message, Modal,
} from "antd";
import { PlusOutlined, EyeOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { getPayments, deletePayment } from "../api/payments";
import type { PaymentListItem } from "../types/payment";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const fmtCny = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PaymentsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [deleteModal, setDeleteModal] = useState<{ open: boolean; paymentId: string | null }>({ open: false, paymentId: null });
  const [deleteReason, setDeleteReason] = useState("");

  const [search, setSearch] = useState("");
  const [direction, setDirection] = useState<string | undefined>();
  const [currency, setCurrency] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [page, setPage] = useState(1);

  const params = {
    search: search || undefined,
    direction,
    currency,
    date_from: dateRange?.[0],
    date_to: dateRange?.[1],
    page,
    page_size: 20,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["payments", params],
    queryFn: () => getPayments(params).then(r => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: deletePayment,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["purchases"] });
      message.success("✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const columns: ColumnsType<PaymentListItem> = [
    {
      title: t("payment.date"),
      dataIndex: "payment_date",
      key: "date",
      width: 110,
    },
    {
      title: t("payment.direction"),
      key: "direction",
      width: 120,
      render: (_, row) => (
        <Tag color={row.direction === "in" ? "green" : "red"}>
          {row.direction === "in" ? t("payment.incoming") : t("payment.outgoing")}
        </Tag>
      ),
    },
    {
      title: t("payment.counterparty"),
      dataIndex: "counterparty_name",
      key: "counterparty",
    },
    {
      title: t("payment.currency"),
      dataIndex: "currency",
      key: "currency",
      width: 80,
    },
    {
      title: t("payment.amount"),
      key: "amount",
      align: "right",
      width: 130,
      render: (_, row) => `${fmtCny(row.amount)} ${row.currency}`,
    },
    {
      title: `${t("payment.amount_cny")} (CNY)`,
      dataIndex: "amount_cny",
      key: "amount_cny",
      align: "right",
      width: 130,
      render: v => fmtCny(v),
    },
    {
      title: t("payment.allocations"),
      key: "alloc",
      width: 150,
      render: (_, row) => {
        const cnt = row.allocations_count;
        if (cnt === 0) return <Text type="secondary">—</Text>;
        return (
          <div>
            <Text>{cnt} {row.direction === "in" ? t("payment.alloc_order") : t("payment.alloc_purchase")}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 11 }}>
              {fmtCny(row.allocated_cny)} / {fmtCny(row.amount_cny)} CNY
            </Text>
          </div>
        );
      },
    },
    {
      title: t("common.created_by"),
      dataIndex: "created_by_name",
      key: "creator",
      width: 120,
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 90,
      render: (_, row) => (
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => navigate(`/payments/${row.id}`)} />
          <Button
            icon={<DeleteOutlined />}
            size="small"
            danger
            onClick={() => { setDeleteReason(""); setDeleteModal({ open: true, paymentId: row.id }); }}
          />
        </Space>
      ),
    },
  ];

  const incoming = data?.total_incoming_cny ?? 0;
  const outgoing = data?.total_outgoing_cny ?? 0;

  const handleDeleteConfirm = () => {
    if (!deleteModal.paymentId || !deleteReason.trim()) return;
    deleteMutation.mutate({ id: deleteModal.paymentId, reason: deleteReason.trim() });
    setDeleteModal({ open: false, paymentId: null });
  };

  return (
    <div>
      <Modal
        open={deleteModal.open}
        title={t("payment.delete_modal_title")}
        onOk={handleDeleteConfirm}
        onCancel={() => setDeleteModal({ open: false, paymentId: null })}
        okText={t("common.delete")}
        cancelText={t("common.cancel")}
        okButtonProps={{ danger: true, disabled: !deleteReason.trim(), loading: deleteMutation.isPending }}
        destroyOnClose
      >
        <p style={{ marginBottom: 8 }}>{t("payment.delete_reason_label")}:</p>
        <Input.TextArea
          rows={3}
          placeholder={t("payment.delete_reason_placeholder")}
          value={deleteReason}
          onChange={e => setDeleteReason(e.target.value)}
          autoFocus
        />
      </Modal>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("payment.title")}</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/payments/new")}>
            {t("payment.create_new")}
          </Button>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Statistic title={t("payment.balance_in")} value={fmtCny(incoming)} valueStyle={{ color: "#389e0d" }} />
        </Col>
        <Col span={6}>
          <Statistic title={t("payment.balance_out")} value={fmtCny(outgoing)} valueStyle={{ color: "#cf1322" }} />
        </Col>
        <Col span={6}>
          <Statistic
            title={t("payment.balance_net")}
            value={fmtCny(incoming - outgoing)}
            valueStyle={{ color: incoming - outgoing >= 0 ? "#389e0d" : "#cf1322" }}
          />
        </Col>
      </Row>

      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col>
          <Input.Search
            placeholder={t("payment.search_placeholder")}
            allowClear
            style={{ width: 220 }}
            onSearch={v => { setSearch(v); setPage(1); }}
            onChange={e => { if (!e.target.value) { setSearch(""); setPage(1); } }}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("payment.filter_direction")}
            style={{ width: 180 }}
            options={[
              { value: "in", label: t("payment.incoming") },
              { value: "out", label: t("payment.outgoing") },
            ]}
            onChange={v => { setDirection(v); setPage(1); }}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("payment.currency")}
            style={{ width: 100 }}
            options={["CNY", "RUB", "USDT", "USD"].map(c => ({ value: c, label: c }))}
            onChange={v => { setCurrency(v); setPage(1); }}
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

      <Table scroll={{ x: "max-content" }}
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
