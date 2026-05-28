import { useState, useMemo } from "react";
import { Button, DatePicker, Table, Typography, Row, Col, Space, Spin, Tag } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import { getBySupplier, exportBySupplier, type BySupplierRow } from "../../api/reports";
import type { ColumnsType } from "antd/es/table";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const fmtCny = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function BySupplierReport() {
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
    queryKey: ["by-supplier", params],
    queryFn: () => getBySupplier(params).then(r => r.data),
  });

  const totals = useMemo(() => {
    if (!data) return null;
    return data.reduce(
      (acc, row) => ({
        total_purchased_cny: acc.total_purchased_cny + Number(row.total_purchased_cny),
        paid_cny: acc.paid_cny + Number(row.paid_cny),
        debt_cny: acc.debt_cny + Number(row.debt_cny),
        count: acc.count + Number(row.count),
      }),
      { total_purchased_cny: 0, paid_cny: 0, debt_cny: 0, count: 0 }
    );
  }, [data]);

  const tableData = useMemo(() => {
    if (!data) return [];
    const rows = [...data];
    if (totals) {
      rows.push({
        supplier_id: "__total__",
        supplier_name: t("common.all"),
        ...totals,
        has_overdue: false,
      } as any);
    }
    return rows;
  }, [data, totals, t]);

  const columns: ColumnsType<BySupplierRow> = [
    { title: t("purchase.supplier"), dataIndex: "supplier_name", key: "supplier_name",
      render: (v, r: any) => r.supplier_id === "__total__" ? <Text strong>{v}</Text> : v },
    { title: t("report.revenue"), dataIndex: "total_purchased_cny", key: "total_purchased_cny", align: "right",
      render: (v, r: any) => r.supplier_id === "__total__" ? <Text strong>{fmtCny(v)}</Text> : fmtCny(v) },
    { title: t("payment.paid"), dataIndex: "paid_cny", key: "paid_cny", align: "right", render: (v) => fmtCny(v) },
    { title: t("report.debt"), dataIndex: "debt_cny", key: "debt_cny", align: "right",
      render: (v) => <Text style={{ color: Number(v) > 0 ? "#cf1322" : undefined }}>{fmtCny(v)}</Text> },
    { title: t("report.order_count"), dataIndex: "count", key: "count", align: "center" },
    { title: t("report.has_overdue"), dataIndex: "has_overdue", key: "has_overdue", align: "center",
      render: (v, r: any) => r.supplier_id !== "__total__" && v ? <Tag color="red">!</Tag> : null },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={5} style={{ margin: 0 }}>{t("report.by_supplier")}</Title></Col>
        <Col>
          <Button icon={<DownloadOutlined />} onClick={() => exportBySupplier({ ...params, lang })}>
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
          rowKey="supplier_id"
          pagination={false}
          size="middle"
        />
      )}
    </div>
  );
}
