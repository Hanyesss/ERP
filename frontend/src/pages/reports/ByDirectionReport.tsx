import { useState, useMemo } from "react";
import { DatePicker, Table, Typography, Spin, Drawer } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import { getByDirection, type ByDirectionRow } from "../../api/reports";
import type { ColumnsType } from "antd/es/table";
import ByClientReport from "./ByClientReport";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const fmtCny = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ByDirectionReport() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const now = dayjs();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    now.startOf("month"),
    now.endOf("month"),
  ]);
  const [selectedDirection, setSelectedDirection] = useState<{ id: string; name: string } | null>(null);

  const params = {
    date_from: dateRange[0].format("YYYY-MM-DD"),
    date_to: dateRange[1].format("YYYY-MM-DD"),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["by-direction", params],
    queryFn: () => getByDirection(params).then(r => r.data),
  });

  const totals = useMemo(() => {
    if (!data) return null;
    return data.reduce(
      (acc, row) => ({
        revenue: acc.revenue + Number(row.revenue),
        paid: acc.paid + Number(row.paid),
        cogs: acc.cogs + Number(row.cogs),
        direct_expenses: acc.direct_expenses + Number(row.direct_expenses),
        net_profit: acc.net_profit + Number(row.net_profit),
        balance: acc.balance + Number(row.balance),
      }),
      { revenue: 0, paid: 0, cogs: 0, direct_expenses: 0, net_profit: 0, balance: 0 }
    );
  }, [data]);

  const tableData = useMemo(() => {
    if (!data) return [];
    const rows = [...data];
    if (totals) {
      rows.push({
        direction_id: "__total__",
        direction_name: t("common.all"),
        direction_name_cn: t("common.all"),
        ...totals,
      } as any);
    }
    return rows;
  }, [data, totals, t]);

  const columns: ColumnsType<ByDirectionRow> = [
    {
      title: t("report.direction"),
      dataIndex: "direction_name",
      key: "direction_name",
      render: (v, r: any) => {
        const name = lang === "zh" && r.direction_name_cn ? r.direction_name_cn : v;
        return r.direction_id === "__total__" ? (
          <Text strong>{name}</Text>
        ) : (
          <Text style={{ color: "#1677ff", cursor: "pointer" }}>{name}</Text>
        );
      },
    },
    {
      title: t("report.revenue"),
      dataIndex: "revenue",
      key: "revenue",
      align: "right",
      render: (v, r: any) => r.direction_id === "__total__" ? <Text strong>{fmtCny(v)}</Text> : fmtCny(v),
    },
    {
      title: t("payment.paid"),
      dataIndex: "paid",
      key: "paid",
      align: "right",
      render: (v) => fmtCny(v),
    },
    {
      title: t("report.cogs"),
      dataIndex: "cogs",
      key: "cogs",
      align: "right",
      render: (v) => fmtCny(v),
    },
    {
      title: t("report.direct_expenses"),
      dataIndex: "direct_expenses",
      key: "direct_expenses",
      align: "right",
      render: (v) => fmtCny(v),
    },
    {
      title: t("report.net_profit"),
      dataIndex: "net_profit",
      key: "net_profit",
      align: "right",
      render: (v, r: any) => (
        <Text strong={r.direction_id === "__total__"} style={{ color: Number(v) >= 0 ? "#389e0d" : "#cf1322" }}>
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
        if (val >= 0) return <Text style={{ color: "#389e0d" }}>+{fmtCny(val)}</Text>;
        return <Text style={{ color: "#cf1322" }}>{fmtCny(Math.abs(val))}</Text>;
      },
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(v) => { if (v?.[0] && v?.[1]) setDateRange([v[0], v[1]]); }}
        />
      </div>
      {isLoading ? <Spin /> : (
        <Table
          dataSource={tableData}
          columns={columns}
          rowKey="direction_id"
          pagination={false}
          size="middle"
          rowClassName={(r: any) => r.direction_id === "__total__" ? "ant-table-summary" : ""}
          onRow={(r: any) => ({
            onClick: () => {
              if (r.direction_id !== "__total__") {
                const name = lang === "zh" && r.direction_name_cn ? r.direction_name_cn : r.direction_name;
                setSelectedDirection({ id: r.direction_id, name });
              }
            },
            style: r.direction_id !== "__total__" ? { cursor: "pointer" } : undefined,
          })}
        />
      )}

      <Drawer
        title={selectedDirection?.name}
        open={!!selectedDirection}
        onClose={() => setSelectedDirection(null)}
        width="80%"
        destroyOnClose
      >
        {selectedDirection && (
          <ByClientReport
            businessTypeId={selectedDirection.id}
            dateRange={dateRange}
          />
        )}
      </Drawer>
    </div>
  );
}
