import { useState } from "react";
import {
  Typography, Row, Col, Card, Statistic, Table, Button, Modal, Form,
  DatePicker, Input, Tag, Space, message,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  getPartnerSummary, getPartnerOrders, getPartnerPayouts, requestPayout,
} from "../api/partner";
import type { PartnerOrder, PartnerPayout, PartnerPayoutStatus } from "../types";

const { RangePicker } = DatePicker;

const STATUS_COLORS: Record<PartnerPayoutStatus, string> = {
  pending: "gold",
  approved: "blue",
  paid: "green",
  rejected: "red",
};

function fmt(n: number | string | undefined): string {
  const v = Number(n ?? 0);
  return v.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PartnerDashboardPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: summary } = useQuery({
    queryKey: ["partner-summary"],
    queryFn: () => getPartnerSummary().then((r) => r.data),
  });
  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ["partner-orders"],
    queryFn: () => getPartnerOrders().then((r) => r.data),
  });
  const { data: payouts = [], isLoading: payoutsLoading } = useQuery({
    queryKey: ["partner-payouts"],
    queryFn: () => getPartnerPayouts().then((r) => r.data),
  });

  const requestMut = useMutation({
    mutationFn: requestPayout,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["partner-payouts"] });
      qc.invalidateQueries({ queryKey: ["partner-summary"] });
      setModalOpen(false);
      form.resetFields();
      message.success(t("common.saved"));
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Error";
      message.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    },
  });

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const range = values.range as [dayjs.Dayjs, dayjs.Dayjs] | undefined;
    requestMut.mutate({
      period_from: range?.[0] ? range[0].format("YYYY-MM-DD") : undefined,
      period_to: range?.[1] ? range[1].format("YYYY-MM-DD") : undefined,
      notes: values.notes || undefined,
    });
  };

  const orderColumns: ColumnsType<PartnerOrder> = [
    { title: t("partner.order_number"), dataIndex: "order_number", key: "order_number" },
    { title: t("partner.client"), dataIndex: "client_name", key: "client_name" },
    { title: t("partner.sale_cny"), dataIndex: "sale_cny", key: "sale_cny", align: "right", render: (v) => fmt(v) },
    { title: t("partner.cost_cny"), dataIndex: "cost_cny", key: "cost_cny", align: "right", render: (v) => fmt(v) },
    { title: t("partner.margin"), dataIndex: "margin_cny", key: "margin_cny", align: "right", render: (v) => fmt(v) },
    { title: t("partner.share"), dataIndex: "share_cny", key: "share_cny", align: "right", render: (v) => <b>{fmt(v)}</b> },
    { title: t("partner.payment_status"), dataIndex: "payment_status", key: "payment_status" },
    { title: t("partner.date"), dataIndex: "order_date", key: "order_date" },
  ];

  const payoutColumns: ColumnsType<PartnerPayout> = [
    { title: t("partner.date"), dataIndex: "created_at", key: "created_at", render: (v) => (v ? dayjs(v).format("YYYY-MM-DD") : "—") },
    {
      title: t("partner.period"), key: "period",
      render: (_, r) => (r.period_from || r.period_to ? `${r.period_from ?? "..."} — ${r.period_to ?? "..."}` : t("partner.all_time")),
    },
    { title: t("partner.amount"), dataIndex: "amount", key: "amount", align: "right", render: (v) => fmt(v) },
    {
      title: t("partner.status"), dataIndex: "status", key: "status",
      render: (s: PartnerPayoutStatus) => <Tag color={STATUS_COLORS[s]}>{t(`partner.payout_status.${s}`)}</Tag>,
    },
    { title: t("partner.notes"), dataIndex: "notes", key: "notes" },
  ];

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {t("nav.partner_dashboard")}
      </Typography.Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card><Statistic title={t("partner.accrued")} value={fmt(summary?.total_accrued)} suffix="¥" /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title={t("partner.paid")} value={fmt(summary?.total_paid)} suffix="¥" /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title={t("partner.balance")}
              value={fmt(summary?.balance)}
              suffix="¥"
              valueStyle={{ color: Number(summary?.balance ?? 0) >= 0 ? "#3f8600" : "#cf1322" }}
            />
          </Card>
        </Col>
      </Row>

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => setModalOpen(true)}>
          {t("partner.request_payout")}
        </Button>
      </Space>

      <Typography.Title level={5}>{t("partner.orders")}</Typography.Title>
      <Table
        scroll={{ x: "max-content" }}
        columns={orderColumns}
        dataSource={orders}
        rowKey="id"
        loading={ordersLoading}
        size="small"
        pagination={{ pageSize: 20 }}
        style={{ marginBottom: 24 }}
      />

      <Typography.Title level={5}>{t("partner.payouts")}</Typography.Title>
      <Table
        scroll={{ x: "max-content" }}
        columns={payoutColumns}
        dataSource={payouts}
        rowKey="id"
        loading={payoutsLoading}
        size="small"
        pagination={{ pageSize: 10 }}
      />

      <Modal
        open={modalOpen}
        title={t("partner.request_payout")}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        onOk={handleSubmit}
        confirmLoading={requestMut.isPending}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="range" label={`${t("partner.period_from")} / ${t("partner.period_to")}`} tooltip={t("partner.all_time")}>
            <RangePicker style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="notes" label={t("partner.notes")}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
