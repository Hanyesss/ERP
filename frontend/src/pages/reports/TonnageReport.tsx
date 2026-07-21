import { useState } from "react";
import { Button, DatePicker, Select, Table, Typography, Row, Col, Space, Spin, Card, Statistic } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getTonnage, exportTonnage, exportTonnageDetail } from "../../api/reports";
import { getWarehouses } from "../../api/warehouses";
import { getCounterparties } from "../../api/counterparties";

const { Title } = Typography;
const { RangePicker } = DatePicker;

const fmtNum = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function TonnageReport() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const now = dayjs();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    now.startOf("month"),
    now.endOf("month"),
  ]);
  const [warehouseId, setWarehouseId] = useState<string | undefined>();
  const [clientId, setClientId] = useState<string | undefined>();
  const [detailLoading, setDetailLoading] = useState<string | null>(null);

  const params = {
    date_from: dateRange[0].format("YYYY-MM-DD"),
    date_to: dateRange[1].format("YYYY-MM-DD"),
    warehouse_id: warehouseId,
    client_id: clientId,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["tonnage", params],
    queryFn: () => getTonnage(params).then(r => r.data),
  });

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => getWarehouses().then(r => r.data),
  });

  const { data: clients } = useQuery({
    queryKey: ["counterparties-clients"],
    queryFn: () => getCounterparties({ type: "client", page_size: 200 }).then(r => r.data),
  });

  const whOptions = [
    { value: "", label: t("report.all_warehouses") },
    ...(warehouses || []).map((wh: any) => ({ value: wh.id, label: wh.name })),
  ];

  const clientOptions = [
    { value: "", label: t("common.all") },
    ...(clients?.items || []).map((c: any) => ({ value: c.id, label: c.name })),
  ];

  // Детализация всегда берёт текущий выбранный период, поэтому работает на любом промежутке
  const handleDetailExport = async (whId?: string, whName?: string) => {
    setDetailLoading(whId ?? "all");
    try {
      await exportTonnageDetail(
        { ...params, warehouse_id: whId ?? params.warehouse_id, lang },
        whName ? `_${whName}` : "",
      );
    } finally {
      setDetailLoading(null);
    }
  };

  const warehouseColumns = [
    {
      title: lang === "zh" ? "仓库" : "Склад",
      key: "warehouse_name",
      render: (r: any) => lang === "zh" ? (r.warehouse_name_cn || r.warehouse_name) : r.warehouse_name,
    },
    { title: t("report.order_count"), dataIndex: "order_count", key: "order_count", align: "center" as const },
    { title: t("report.total_weight"), dataIndex: "total_weight_kg", key: "total_weight_kg", align: "right" as const, render: (v: number) => fmtNum(v) },
    { title: t("report.total_volume"), dataIndex: "total_volume_m3", key: "total_volume_m3", align: "right" as const, render: (v: number) => fmtNum(v) },
    {
      title: t("report.download_excel"),
      key: "detail_export",
      align: "center" as const,
      width: 160,
      render: (r: any) => (
        <Button
          size="small"
          icon={<DownloadOutlined />}
          loading={detailLoading === r.warehouse_id}
          onClick={() => handleDetailExport(r.warehouse_id, r.warehouse_name)}
        >
          {t("report.download_excel")}
        </Button>
      ),
    },
  ];

  const monthChartData = (data?.by_month || []).map(m => ({
    label: `${m.year}-${String(m.month).padStart(2, "0")}`,
    weight: Number(m.total_weight_kg),
    volume: Number(m.total_volume_m3),
  }));

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={5} style={{ margin: 0 }}>{t("report.tonnage")}</Title></Col>
        <Col>
          <Space>
            <Button
              icon={<DownloadOutlined />}
              loading={detailLoading === "all"}
              onClick={() => handleDetailExport()}
            >
              {t("report.export_detail_excel")}
            </Button>
            <Button icon={<DownloadOutlined />} onClick={() => exportTonnage({ ...params, lang })}>
              {t("report.export_excel")}
            </Button>
          </Space>
        </Col>
      </Row>

      <Space wrap style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(v) => { if (v?.[0] && v?.[1]) setDateRange([v[0], v[1]]); }}
        />
        <Select
          style={{ minWidth: 160 }}
          options={whOptions}
          value={warehouseId || ""}
          onChange={v => setWarehouseId(v || undefined)}
        />
        <Select
          style={{ minWidth: 160 }}
          options={clientOptions}
          value={clientId || ""}
          onChange={v => setClientId(v || undefined)}
          showSearch
          filterOption={(input, option) =>
            (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
          }
        />
      </Space>

      {isLoading ? <Spin /> : (
        <>
          {/* Summary cards */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title={t("report.total_weight")}
                  value={Number(data?.total_weight_kg || 0).toFixed(2)}
                  suffix="кг"
                />
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title={t("report.total_volume")}
                  value={Number(data?.total_volume_m3 || 0).toFixed(2)}
                  suffix="м³"
                />
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title={t("report.order_count")}
                  value={data?.order_count || 0}
                />
              </Card>
            </Col>
          </Row>

          {/* By warehouse table */}
          {(data?.by_warehouse || []).length > 0 && (
            <>
              <Title level={5}>{t("report.by_warehouse")}</Title>
              <Table
                dataSource={data?.by_warehouse || []}
                columns={warehouseColumns}
                rowKey="warehouse_id"
                pagination={false}
                size="small"
                style={{ marginBottom: 24 }}
              />
            </>
          )}

          {/* By month chart */}
          {monthChartData.length > 0 && (
            <>
              <Title level={5}>{t("report.by_month")}</Title>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={monthChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="weight" fill="#4472C4" name={t("report.total_weight")} />
                  <Bar dataKey="volume" fill="#ED7D31" name={t("report.total_volume")} />
                </BarChart>
              </ResponsiveContainer>
            </>
          )}
        </>
      )}
    </div>
  );
}
