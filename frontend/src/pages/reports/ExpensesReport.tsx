import { useState } from "react";
import { Button, DatePicker, Select, Table, Typography, Row, Col, Space, Spin } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getExpensesReport, exportExpenses } from "../../api/reports";

const { Title } = Typography;
const { RangePicker } = DatePicker;

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884D8", "#82ca9d", "#ffc658", "#a4de6c", "#d0ed57", "#ffa8a8"];

const fmtCny = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ExpensesReport() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const now = dayjs();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    now.startOf("month"),
    now.endOf("month"),
  ]);
  const [linkType, setLinkType] = useState<string | undefined>();

  const params = {
    date_from: dateRange[0].format("YYYY-MM-DD"),
    date_to: dateRange[1].format("YYYY-MM-DD"),
    link_type: linkType,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["expenses-report", params],
    queryFn: () => getExpensesReport(params).then(r => r.data),
  });

  const pieData = (data?.items || []).map(c => ({
    name: lang === "zh" ? (c.category_name_cn || c.category_name) : c.category_name,
    value: Number(c.amount_cny),
  }));

  const columns = [
    {
      title: lang === "zh" ? "类别" : "Категория",
      dataIndex: lang === "zh" ? "category_name_cn" : "category_name",
      key: "category_name",
    },
    {
      title: "CNY",
      dataIndex: "amount_cny",
      key: "amount_cny",
      align: "right" as const,
      render: (v: number) => fmtCny(v),
    },
    {
      title: "%",
      dataIndex: "percent",
      key: "percent",
      align: "right" as const,
      render: (v: number) => `${v.toFixed(1)}%`,
    },
    {
      title: t("report.order_count"),
      dataIndex: "count",
      key: "count",
      align: "center" as const,
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={5} style={{ margin: 0 }}>{t("report.expenses_structure")}</Title></Col>
        <Col>
          <Button icon={<DownloadOutlined />} onClick={() => exportExpenses({ ...params, lang })}>
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
          allowClear
          placeholder={t("common.all")}
          value={linkType}
          onChange={v => setLinkType(v)}
          options={[
            { value: "order", label: t("expense.link_order") },
            { value: "client", label: t("expense.link_client") },
            { value: "none", label: t("expense.link_none") },
          ]}
        />
      </Space>

      {isLoading ? <Spin /> : (
        <Row gutter={24}>
          <Col xs={24} lg={12}>
            {pieData.length > 0 && (
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    outerRadius={110}
                    dataKey="value"
                    label={({ name, percent }: any) => `${((percent ?? 0) * 100).toFixed(1)}%`}
                  >
                    {pieData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: any) => fmtCny(Number(v))} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Col>
          <Col xs={24} lg={12}>
            <Table
              dataSource={data?.items || []}
              columns={columns}
              rowKey="category_name"
              pagination={false}
              size="small"
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0}><strong>{t("common.all")}</strong></Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right"><strong>{fmtCny(data?.total || 0)}</strong></Table.Summary.Cell>
                  <Table.Summary.Cell index={2} align="right"><strong>100%</strong></Table.Summary.Cell>
                  <Table.Summary.Cell index={3} />
                </Table.Summary.Row>
              )}
            />
          </Col>
        </Row>
      )}
    </div>
  );
}
