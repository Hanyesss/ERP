import { useState, useMemo } from "react";
import { Button, DatePicker, Table, Typography, Row, Col, Space, Spin, Input } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { SearchOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import { getByClient, exportByClient, type ByClientRow } from "../../api/reports";
import type { ColumnsType } from "antd/es/table";
import ClientDetailDrawer from "./ClientDetailDrawer";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const fmtCny = (v: number | string | null | undefined) => {
  const n = Number(v ?? 0);
  return (isNaN(n) ? 0 : n).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

interface Props {
  businessTypeId?: string;
  dateRange?: [dayjs.Dayjs, dayjs.Dayjs];
}

export default function ByClientReport({ businessTypeId, dateRange: externalDateRange }: Props = {}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const now = dayjs();
  const [internalDateRange, setInternalDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    now.startOf("month"),
    now.endOf("month"),
  ]);
  const [clientSearch, setClientSearch] = useState("");
  const [selectedClient, setSelectedClient] = useState<{ id: string; name: string } | null>(null);

  const dateRange = externalDateRange ?? internalDateRange;
  const isEmbedded = !!externalDateRange;

  const params = {
    date_from: dateRange[0].format("YYYY-MM-DD"),
    date_to: dateRange[1].format("YYYY-MM-DD"),
    business_type_id: businessTypeId,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["by-client", params],
    queryFn: () => getByClient(params).then(r => r.data),
  });

  const filteredData = useMemo(() => {
    if (!data) return [];
    if (!clientSearch.trim()) return data;
    const q = clientSearch.trim().toLowerCase();
    return data.filter(r => r.client_name.toLowerCase().includes(q));
  }, [data, clientSearch]);

  const totals = useMemo(() => {
    if (!filteredData.length) return null;
    return filteredData.reduce(
      (acc, row) => ({
        revenue: acc.revenue + Number(row.revenue),
        paid_by_client: acc.paid_by_client + Number(row.paid_by_client),
        paid_to_supplier: acc.paid_to_supplier + Number(row.paid_to_supplier),
        unallocated_cny: acc.unallocated_cny + Number(row.unallocated_cny ?? 0),
        cogs: acc.cogs + Number(row.cogs),
        direct_expenses: acc.direct_expenses + Number(row.direct_expenses),
        client_expenses: acc.client_expenses + Number(row.client_expenses),
        net_profit: acc.net_profit + Number(row.net_profit),
        balance: acc.balance + Number(row.balance),
      }),
      { revenue: 0, paid_by_client: 0, paid_to_supplier: 0, unallocated_cny: 0, cogs: 0, direct_expenses: 0, client_expenses: 0, net_profit: 0, balance: 0 }
    );
  }, [filteredData]);

  const tableData = useMemo(() => {
    const rows = [...filteredData];
    if (totals) {
      rows.push({
        client_id: "__total__",
        client_name: t("common.all"),
        ...totals,
      } as any);
    }
    return rows;
  }, [filteredData, totals, t]);

  const columns: ColumnsType<ByClientRow> = [
    {
      title: t("order.client"),
      dataIndex: "client_name",
      key: "client_name",
      render: (v, r: any) =>
        r.client_id === "__total__" ? (
          <Text strong>{v}</Text>
        ) : (
          <Text style={{ color: "#1677ff", cursor: "pointer" }}>{v}</Text>
        ),
    },
    {
      title: t("report.revenue"),
      dataIndex: "revenue",
      key: "revenue",
      align: "right",
      render: (v, r: any) => r.client_id === "__total__" ? <Text strong>{fmtCny(v)}</Text> : fmtCny(v),
    },
    { title: t("report.paid_by_client"), dataIndex: "paid_by_client", key: "paid_by_client", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.paid_to_supplier"), dataIndex: "paid_to_supplier", key: "paid_to_supplier", align: "right", render: (v) => fmtCny(v) },
    {
      title: t("payment.unallocated"),
      dataIndex: "unallocated_cny",
      key: "unallocated_cny",
      align: "right",
      render: (v: number) => Number(v) > 0
        ? <Text style={{ color: "#faad14" }}>{fmtCny(v)}</Text>
        : <Text type="secondary">—</Text>,
    },
    { title: t("report.cogs"), dataIndex: "cogs", key: "cogs", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.direct_expenses"), dataIndex: "direct_expenses", key: "direct_expenses", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.client_expenses"), dataIndex: "client_expenses", key: "client_expenses", align: "right", render: (v) => fmtCny(v) },
    {
      title: t("report.net_profit"),
      dataIndex: "net_profit",
      key: "net_profit",
      align: "right",
      render: (v, r: any) => (
        <Text strong={r.client_id === "__total__"} style={{ color: Number(v) >= 0 ? "#389e0d" : "#cf1322" }}>
          {fmtCny(v)}
        </Text>
      ),
    },
    {
      title: t("report.debt"),
      dataIndex: "balance",
      key: "balance",
      align: "right",
      render: (v) => {
        const val = Number(v);
        if (val >= 0) {
          return <Text style={{ color: "#389e0d" }}>+{fmtCny(val)}</Text>;
        }
        return <Text style={{ color: "#cf1322" }}>{fmtCny(Math.abs(val))}</Text>;
      },
    },
  ];

  return (
    <div>
      {!isEmbedded && (
        <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
          <Col><Title level={5} style={{ margin: 0 }}>{t("report.by_client")}</Title></Col>
          <Col>
            <Button icon={<DownloadOutlined />} onClick={() => exportByClient({ ...params, lang })}>
              {t("report.export_excel")}
            </Button>
          </Col>
        </Row>
      )}
      <Space wrap style={{ marginBottom: 16 }}>
        {!isEmbedded && (
          <RangePicker
            value={internalDateRange}
            onChange={(v) => { if (v?.[0] && v?.[1]) setInternalDateRange([v[0], v[1]]); }}
          />
        )}
        <Input
          prefix={<SearchOutlined />}
          placeholder={t("order.client")}
          value={clientSearch}
          onChange={e => setClientSearch(e.target.value)}
          allowClear
          style={{ width: 200 }}
        />
        {!isEmbedded && (
          <Button icon={<DownloadOutlined />} onClick={() => exportByClient({ ...params, lang })}>
            {t("report.export_excel")}
          </Button>
        )}
      </Space>
      {isLoading ? <Spin /> : (
        <Table
          dataSource={tableData}
          columns={columns}
          rowKey="client_id"
          pagination={false}
          size="middle"
          rowClassName={(r: any) => r.client_id === "__total__" ? "ant-table-summary" : ""}
          onRow={(r: any) => ({
            onClick: () => {
              if (r.client_id !== "__total__") {
                setSelectedClient({ id: r.client_id, name: r.client_name });
              }
            },
            style: r.client_id !== "__total__" ? { cursor: "pointer" } : undefined,
          })}
        />
      )}

      <ClientDetailDrawer
        clientId={selectedClient?.id ?? null}
        clientName={selectedClient?.name ?? ""}
        dateFrom={params.date_from}
        dateTo={params.date_to}
        onClose={() => setSelectedClient(null)}
      />
    </div>
  );
}
