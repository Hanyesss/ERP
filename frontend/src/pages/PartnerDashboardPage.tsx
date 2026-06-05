import { useState, useMemo } from "react";
import {
  Typography, Row, Col, Card, Statistic, Table, Button, Modal, Form,
  DatePicker, Input, Tag, Space, Select, message, Empty,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  getPartnerSummary, getPartnerOrders, getPartnerPayouts, requestPayout,
  type PartnerFilters,
} from "../api/partner";
import { getBusinessTypes } from "../api/references";
import type { PartnerOrder, PartnerPayout, PartnerPayoutStatus } from "../types";

const { RangePicker } = DatePicker;

const COLORS = ["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2", "#eb2f96"];

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

function fmtTon(kg: number | undefined): string {
  const v = Number(kg ?? 0) / 1000;
  return v.toLocaleString("ru-RU", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

type Preset = "week" | "month" | "quarter" | "year";

function presetRange(preset: Preset): [string, string] {
  const now = dayjs();
  switch (preset) {
    case "week":    return [now.startOf("week").format("YYYY-MM-DD"), now.endOf("week").format("YYYY-MM-DD")];
    case "month":   return [now.startOf("month").format("YYYY-MM-DD"), now.endOf("month").format("YYYY-MM-DD")];
    case "quarter": return [now.startOf("quarter").format("YYYY-MM-DD"), now.endOf("quarter").format("YYYY-MM-DD")];
    case "year":    return [now.startOf("year").format("YYYY-MM-DD"), now.endOf("year").format("YYYY-MM-DD")];
  }
}

// Build monthly bar data from orders
function buildMonthlyData(orders: PartnerOrder[]) {
  const map: Record<string, { share: number; weight_t: number }> = {};
  for (const o of orders) {
    const month = o.order_date.slice(0, 7);
    if (!map[month]) map[month] = { share: 0, weight_t: 0 };
    map[month].share += Number(o.share_cny);
    map[month].weight_t += (o.weight_kg ?? 0) / 1000;
  }
  return Object.entries(map)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([month, v]) => ({ month, share: +v.share.toFixed(2), weight_t: +v.weight_t.toFixed(3) }));
}

// Build client pie data from orders
function buildClientData(orders: PartnerOrder[]) {
  const map: Record<string, number> = {};
  for (const o of orders) {
    const name = o.client_name ?? o.client_id;
    map[name] = (map[name] ?? 0) + Number(o.share_cny);
  }
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value: +value.toFixed(2) }));
}

export default function PartnerDashboardPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const [activePreset, setActivePreset] = useState<Preset | null>(null);
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [clientId, setClientId] = useState<string | undefined>();
  const [businessTypeId, setBusinessTypeId] = useState<string | undefined>();

  const filters: PartnerFilters = {
    date_from: dateRange?.[0],
    date_to: dateRange?.[1],
    client_id: clientId,
    business_type_id: businessTypeId,
  };

  const { data: summary } = useQuery({
    queryKey: ["partner-summary", filters],
    queryFn: () => getPartnerSummary(filters).then((r) => r.data),
  });
  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ["partner-orders", filters],
    queryFn: () => getPartnerOrders(filters).then((r) => r.data),
  });
  const { data: payouts = [], isLoading: payoutsLoading } = useQuery({
    queryKey: ["partner-payouts"],
    queryFn: () => getPartnerPayouts().then((r) => r.data),
  });
  const { data: businessTypes = [] } = useQuery({
    queryKey: ["business-types"],
    queryFn: () => getBusinessTypes().then((r) => r.data),
  });

  const clientOptions = (summary?.clients ?? []).map((c) => ({
    value: c.id,
    label: c.code ? `${c.code} — ${c.name}` : c.name,
  }));
  const btOptions = businessTypes.map((bt: any) => ({ value: bt.id, label: bt.name }));

  const monthlyData = useMemo(() => buildMonthlyData(orders), [orders]);
  const clientData  = useMemo(() => buildClientData(orders),  [orders]);

  const handlePreset = (preset: Preset) => {
    if (activePreset === preset) {
      setActivePreset(null);
      setDateRange(null);
    } else {
      setActivePreset(preset);
      setDateRange(presetRange(preset));
    }
  };

  const handleRangeChange = (vals: [Dayjs | null, Dayjs | null] | null) => {
    setActivePreset(null);
    if (vals && vals[0] && vals[1]) {
      setDateRange([vals[0].format("YYYY-MM-DD"), vals[1].format("YYYY-MM-DD")]);
    } else {
      setDateRange(null);
    }
  };

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
    const range = values.range as [Dayjs, Dayjs] | undefined;
    requestMut.mutate({
      period_from: range?.[0] ? range[0].format("YYYY-MM-DD") : undefined,
      period_to: range?.[1] ? range[1].format("YYYY-MM-DD") : undefined,
      notes: values.notes || undefined,
    });
  };

  const presets: { key: Preset; label: string }[] = [
    { key: "week",    label: t("partner.filter.week") },
    { key: "month",   label: t("partner.filter.month") },
    { key: "quarter", label: t("partner.filter.quarter") },
    { key: "year",    label: t("partner.filter.year") },
  ];

  const orderColumns: ColumnsType<PartnerOrder> = [
    { title: t("partner.order_number"), dataIndex: "order_number", key: "order_number" },
    { title: t("partner.client"), dataIndex: "client_name", key: "client_name" },
    { title: t("common.type"), dataIndex: "business_type_name", key: "business_type_name", render: (v) => v ?? "—" },
    { title: t("partner.sale_cny"), dataIndex: "sale_cny", key: "sale_cny", align: "right", render: (v) => fmt(v) },
    { title: t("partner.cost_cny"), dataIndex: "cost_cny", key: "cost_cny", align: "right", render: (v) => fmt(v) },
    { title: t("partner.margin"), dataIndex: "margin_cny", key: "margin_cny", align: "right", render: (v) => fmt(v) },
    { title: t("partner.share"), dataIndex: "share_cny", key: "share_cny", align: "right", render: (v) => <b>{fmt(v)}</b> },
    {
      title: t("partner.weight_t"), dataIndex: "weight_kg", key: "weight_kg", align: "right",
      render: (v) => v != null ? fmtTon(v) : "—",
    },
    {
      title: t("partner.expenses_cny"), dataIndex: "expenses_cny", key: "expenses_cny", align: "right",
      render: (v) => v != null ? fmt(v) : "—",
    },
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

      {/* Filter bar */}
      <Space wrap style={{ marginBottom: 16 }}>
        {presets.map((p) => (
          <Button
            key={p.key}
            type={activePreset === p.key ? "primary" : "default"}
            size="small"
            onClick={() => handlePreset(p.key)}
          >
            {p.label}
          </Button>
        ))}
        <RangePicker
          size="small"
          value={dateRange && !activePreset
            ? [dayjs(dateRange[0]), dayjs(dateRange[1])]
            : null}
          onChange={handleRangeChange as any}
          allowClear
        />
        <Select
          size="small"
          style={{ minWidth: 160 }}
          allowClear
          placeholder={t("partner.filter.client")}
          options={clientOptions}
          value={clientId}
          onChange={(v) => setClientId(v)}
        />
        <Select
          size="small"
          style={{ minWidth: 140 }}
          allowClear
          placeholder={t("partner.filter.type")}
          options={btOptions}
          value={businessTypeId}
          onChange={(v) => setBusinessTypeId(v)}
        />
      </Space>

      {/* Summary cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={6}>
          <Card><Statistic title={t("partner.accrued")} value={fmt(summary?.total_accrued)} suffix="¥" /></Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card><Statistic title={t("partner.paid")} value={fmt(summary?.total_paid)} suffix="¥" /></Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title={t("partner.balance")}
              value={fmt(summary?.balance)}
              suffix="¥"
              valueStyle={{ color: Number(summary?.balance ?? 0) >= 0 ? "#3f8600" : "#cf1322" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title={t("partner.tonnage")}
              value={fmtTon(summary?.total_weight_kg)}
              suffix="т"
            />
          </Card>
        </Col>
      </Row>

      {/* Charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={14}>
          <Card title={t("partner.chart.monthly_share")} size="small">
            {monthlyData.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("common.no_data")} style={{ padding: "24px 0" }} />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={monthlyData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => (v / 1000).toFixed(0) + "K"} />
                  <RTooltip
                    formatter={(v: any, name: any) =>
                      name === "share"
                        ? [(v as number).toLocaleString("ru-RU", { maximumFractionDigits: 0 }) + " ¥", t("partner.share")]
                        : [(v as number).toFixed(3) + " т", t("partner.tonnage")]
                    }
                  />
                  <Legend formatter={(v) => v === "share" ? t("partner.share") : t("partner.tonnage")} />
                  <Bar dataKey="share" fill="#1890ff" name="share" />
                  <Bar dataKey="weight_t" fill="#52c41a" name="weight_t" yAxisId={0} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title={t("partner.chart.share_by_client")} size="small">
            {clientData.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("common.no_data")} style={{ padding: "24px 0" }} />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={clientData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={75}
                    label={({ name, percent }: any) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {clientData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <RTooltip
                    formatter={(v: any) =>
                      (v as number).toLocaleString("ru-RU", { maximumFractionDigits: 0 }) + " ¥"
                    }
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
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
