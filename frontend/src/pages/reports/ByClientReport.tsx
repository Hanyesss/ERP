import { useState, useMemo } from "react";
import { Button, DatePicker, Table, Typography, Row, Col, Space, Spin } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import { getByClient, exportByClient, type ByClientRow } from "../../api/reports";
import type { ColumnsType } from "antd/es/table";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const fmtCny = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ByClientReport() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const now = dayjs();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    now.startOf("month"),
    now.endOf("month"),
  ]);

  const params = {
    date_from: dateRange[0].format("YYYY-MM-DD"),
    date_to: dateRange[1].format("YYYY-MM-DD"),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["by-client", params],
    queryFn: () => getByClient(params).then(r => r.data),
  });

  const totals = useMemo(() => {
    if (!data) return null;
    return data.reduce(
      (acc, row) => ({
        revenue: acc.revenue + Number(row.revenue),
        paid: acc.paid + Number(row.paid),
        cogs: acc.cogs + Number(row.cogs),
        direct_expenses: acc.direct_expenses + Number(row.direct_expenses),
        client_expenses: acc.client_expenses + Number(row.client_expenses),
        net_profit: acc.net_profit + Number(row.net_profit),
        debt: acc.debt + Number(row.debt),
      }),
      { revenue: 0, paid: 0, cogs: 0, direct_expenses: 0, client_expenses: 0, net_profit: 0, debt: 0 }
    );
  }, [data]);

  const tableData = useMemo(() => {
    if (!data) return [];
    const rows = [...data];
    if (totals) {
      rows.push({
        client_id: "__total__",
        client_name: t("common.all"),
        ...totals,
      } as any);
    }
    return rows;
  }, [data, totals, t]);

  const columns: ColumnsType<ByClientRow> = [
    { title: t("order.client"), dataIndex: "client_name", key: "client_name",
      render: (v, r: any) => r.client_id === "__total__" ? <Text strong>{v}</Text> : v },
    { title: t("report.revenue"), dataIndex: "revenue", key: "revenue", align: "right",
      render: (v, r: any) => r.client_id === "__total__" ? <Text strong>{fmtCny(v)}</Text> : fmtCny(v) },
    { title: t("payment.paid"), dataIndex: "paid", key: "paid", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.cogs"), dataIndex: "cogs", key: "cogs", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.direct_expenses"), dataIndex: "direct_expenses", key: "direct_expenses", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.client_expenses"), dataIndex: "client_expenses", key: "client_expenses", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.net_profit"), dataIndex: "net_profit", key: "net_profit", align: "right",
      render: (v, r: any) => (
        <Text strong={r.client_id === "__total__"} style={{ color: Number(v) >= 0 ? "#389e0d" : "#cf1322" }}>
          {fmtCny(v)}
        </Text>
      ) },
    { title: t("report.debt"), dataIndex: "debt", key: "debt", align: "right",
      render: (v) => <Text style={{ color: Number(v) > 0 ? "#cf1322" : undefined }}>{fmtCny(v)}</Text> },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={5} style={{ margin: 0 }}>{t("report.by_client")}</Title></Col>
        <Col>
          <Button icon={<DownloadOutlined />} onClick={() => exportByClient({ ...params, lang })}>
            {t("report.export_excel")}
          </Button>
        </Col>
      </Row>
      <Space style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(v) => { if (v?.[0] && v?.[1]) setDateRange([v[0], v[1]]); }}
        />
      </Space>
      {isLoading ? <Spin /> : (
        <Table
          dataSource={tableData}
          columns={columns}
          rowKey="client_id"
          pagination={false}
          size="middle"
          rowClassName={(r: any) => r.client_id === "__total__" ? "ant-table-summary" : ""}
        />
      )}
    </div>
  );
}
