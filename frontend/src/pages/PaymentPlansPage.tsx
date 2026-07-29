import { useState } from "react";
import { Typography, Table, Tag, Input, Select, Row, Col, Button, Space } from "antd";
import { DollarOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import TopScrollTable from "../components/common/TopScrollTable";
import { getPaymentPlans, type PaymentPlan } from "../api/paymentPlans";
import PlanSettleModal from "../components/payments/PlanSettleModal";

const { Title } = Typography;

const fmt = (v?: number | null) =>
  v == null ? "—" : Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const STATUS_COLOR: Record<string, string> = { pending: "gold", deposit: "blue", paid: "green" };

export default function PaymentPlansPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [direction, setDirection] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<PaymentPlan | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["payment-plans", search, direction, status, page],
    queryFn: () => getPaymentPlans({
      search: search || undefined, direction, status, page, page_size: 20,
    }).then(r => r.data),
  });

  const columns = [
    { title: t("plan.doc"), dataIndex: "doc_number", key: "doc", render: (v: string) => v || "—" },
    { title: t("plan.direction"), key: "dir", width: 110,
      render: (_: any, r: PaymentPlan) => (
        <Tag color={r.direction === "in" ? "green" : "red"}>
          {r.direction === "in" ? t("payment.incoming") : t("payment.outgoing")}
        </Tag>
      ) },
    { title: t("plan.counterparty"), dataIndex: "counterparty_name", key: "cp", render: (v: string) => v || "—" },
    { title: t("plan.expected"), dataIndex: "expected_cny", key: "exp", align: "right" as const,
      render: (v: number) => `${fmt(v)} CNY` },
    { title: t("plan.paid"), dataIndex: "paid_cny", key: "paid", align: "right" as const,
      render: (v: number) => fmt(v) },
    { title: t("plan.remaining"), dataIndex: "remaining_cny", key: "rem", align: "right" as const,
      render: (v: number) => <span style={{ color: v > 0 ? "#cf1322" : "#3f8600" }}>{fmt(v)}</span> },
    { title: t("plan.status"), dataIndex: "status", key: "st", width: 140,
      render: (s: string) => <Tag color={STATUS_COLOR[s]}>{t(`plan.status_${s}`)}</Tag> },
    { title: t("plan.installments_count"), key: "inst", width: 90, align: "center" as const,
      render: (_: any, r: PaymentPlan) => r.installments.length || "—" },
    { title: "", key: "act", width: 130,
      render: (_: any, r: PaymentPlan) => (
        <Button size="small" type={r.status === "paid" ? "default" : "primary"}
          icon={<DollarOutlined />} onClick={() => setSelected(r)}>
          {r.status === "paid" ? t("plan.view") : t("plan.settle")}
        </Button>
      ) },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={4} style={{ margin: 0 }}>{t("plan.title")}</Title></Col>
      </Row>

      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search placeholder={t("plan.search")} allowClear style={{ width: 240 }}
          onSearch={v => { setSearch(v); setPage(1); }}
          onChange={e => { if (!e.target.value) { setSearch(""); setPage(1); } }} />
        <Select allowClear placeholder={t("plan.direction")} style={{ width: 150 }}
          value={direction} onChange={v => { setDirection(v); setPage(1); }}
          options={[
            { value: "in", label: t("payment.incoming") },
            { value: "out", label: t("payment.outgoing") },
          ]} />
        <Select allowClear placeholder={t("plan.status")} style={{ width: 180 }}
          value={status} onChange={v => { setStatus(v); setPage(1); }}
          options={["pending", "deposit", "paid"].map(s => ({ value: s, label: t(`plan.status_${s}`) }))} />
      </Space>

      <TopScrollTable
        columns={columns}
        dataSource={data?.items || []}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{ current: page, pageSize: 20, total: data?.total || 0, onChange: setPage, showSizeChanger: false }}
      />

      <PlanSettleModal plan={selected} open={!!selected} onClose={() => setSelected(null)} />
    </div>
  );
}
