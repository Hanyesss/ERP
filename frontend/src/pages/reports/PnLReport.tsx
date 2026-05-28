import { useState, useMemo } from "react";
import {
  Button, DatePicker, Select, Table, Typography, Row, Col, Space, Spin, Tag,
} from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getPnL, exportPnL, type PnLData } from "../../api/reports";
import { getWarehouses } from "../../api/warehouses";
import { getBusinessTypes } from "../../api/references";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884D8", "#82ca9d", "#ffc658", "#a4de6c"];

const fmtCny = (v: number | undefined) =>
  v != null ? Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${v > 0 ? "+" : ""}${v.toFixed(1)}%` : "—";

export default function PnLReport() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;

  const now = dayjs();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    now.startOf("month"),
    now.endOf("month"),
  ]);
  const [businessTypeId, setBusinessTypeId] = useState<string | undefined>();
  const [warehouseId, setWarehouseId] = useState<string | undefined>();

  const params = {
    date_from: dateRange[0].format("YYYY-MM-DD"),
    date_to: dateRange[1].format("YYYY-MM-DD"),
    business_type_id: businessTypeId,
    warehouse_id: warehouseId,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["pnl", params],
    queryFn: () => getPnL(params).then(r => r.data),
    enabled: !!dateRange,
  });

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => getWarehouses().then(r => r.data),
  });

  const { data: businessTypes } = useQuery({
    queryKey: ["business-types"],
    queryFn: () => getBusinessTypes().then(r => r.data),
  });

  const tableData = useMemo(() => {
    if (!data) return [];
    const prev = data.prev_period;
    return [
      { key: "revenue", label: t("report.revenue"), value: data.revenue, prevValue: prev.revenue, pct: data.pct_revenue, bold: false, positive: true },
      { key: "cogs", label: `− ${t("report.cogs")}`, value: data.cogs, prevValue: prev.cogs, pct: null, bold: false, positive: false },
      { key: "direct_exp", label: `− ${t("report.direct_expenses")}`, value: data.direct_expenses, prevValue: prev.direct_expenses, pct: null, bold: false, positive: false },
      { key: "gross", label: `= ${t("report.gross_profit")}`, value: data.gross_profit, prevValue: prev.gross_profit, pct: data.pct_gross_profit, bold: true, positive: data.gross_profit >= 0 },
      { key: "client_exp", label: `− ${t("report.client_expenses")}`, value: data.client_expenses, prevValue: prev.client_expenses, pct: null, bold: false, positive: false },
      { key: "general_exp", label: `− ${t("report.general_expenses")}`, value: data.general_expenses, prevValue: prev.general_expenses, pct: null, bold: false, positive: false },
      { key: "net", label: `= ${t("report.net_profit")}`, value: data.net_profit, prevValue: prev.net_profit, pct: data.pct_net_profit, bold: true, positive: data.net_profit >= 0 },
    ];
  }, [data, t]);

  const pieData = useMemo(() => {
    if (!data?.expenses_by_category) return [];
    return data.expenses_by_category.map(c => ({
      name: lang === "zh" ? (c.category_name_cn || c.category_name) : c.category_name,
      value: Number(c.amount_cny),
    }));
  }, [data, lang]);

  const columns = [
    {
      title: t("report.period"),
      dataIndex: "label",
      key: "label",
      render: (v: string, r: any) => (
        <Text strong={r.bold}>{v}</Text>
      ),
    },
    {
      title: `${params.date_from} — ${params.date_to}`,
      dataIndex: "value",
      key: "value",
      align: "right" as const,
      render: (v: number, r: any) => (
        <Text strong={r.bold} style={{ color: r.key.includes("gross") || r.key === "net" ? (r.positive ? "#389e0d" : "#cf1322") : undefined }}>
          {fmtCny(v)}
        </Text>
      ),
    },
    {
      title: t("report.prev_period"),
      dataIndex: "prevValue",
      key: "prevValue",
      align: "right" as const,
      render: (v: number, r: any) => <Text type="secondary">{fmtCny(v)}</Text>,
    },
    {
      title: t("report.change_pct"),
      dataIndex: "pct",
      key: "pct",
      align: "right" as const,
      render: (v: number | null) => {
        if (v === null || v === undefined) return "—";
        const color = v >= 0 ? "#389e0d" : "#cf1322";
        return <Text style={{ color }}>{fmtPct(v)}</Text>;
      },
    },
  ];

  const btOptions = [
    { value: "", label: t("report.all_types") },
    ...(businessTypes || []).map((bt: any) => ({ value: bt.id, label: bt.name })),
  ];

  const whOptions = [
    { value: "", label: t("report.all_warehouses") },
    ...(warehouses || []).map((wh: any) => ({ value: wh.id, label: wh.name })),
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={5} style={{ margin: 0 }}>{t("report.pnl")}</Title>
        </Col>
        <Col>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => exportPnL({ ...params, lang })}
          >
            {t("report.export_excel")}
          </Button>
        </Col>
      </Row>

      <Space wrap style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(v) => { if (v?.[0] && v?.[1]) setDateRange([v[0], v[1]]); }}
        />
        <Select
          style={{ minWidth: 150 }}
          options={btOptions}
          value={businessTypeId || ""}
          onChange={v => setBusinessTypeId(v || undefined)}
        />
        <Select
          style={{ minWidth: 150 }}
          options={whOptions}
          value={warehouseId || ""}
          onChange={v => setWarehouseId(v || undefined)}
        />
      </Space>

      {isLoading ? (
        <Spin />
      ) : (
        <>
          <Table
            dataSource={tableData}
            columns={columns}
            rowKey="key"
            pagination={false}
            size="middle"
            style={{ marginBottom: 24 }}
          />

          {pieData.length > 0 && (
            <>
              <Title level={5}>{t("report.expenses_structure")}</Title>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    dataKey="value"
                    label={({ name, percent }: any) => `${name}: ${((percent ?? 0) * 100).toFixed(1)}%`}
                    labelLine={false}
                  >
                    {pieData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: any) => fmtCny(Number(v))} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </>
          )}
        </>
      )}
    </div>
  );
}
