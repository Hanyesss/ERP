import { Drawer, Table, Typography, Descriptions, Spin, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getClientDetail, type ClientOrderRow } from "../../api/reports";
import type { ColumnsType } from "antd/es/table";

const { Text } = Typography;

const fmtCny = (v: number | string | null | undefined) =>
  Number(v ?? 0).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props {
  clientId: string | null;
  clientName: string;
  dateFrom: string;
  dateTo: string;
  onClose: () => void;
}

export default function ClientDetailDrawer({ clientId, clientName, dateFrom, dateTo, onClose }: Props) {
  const { t } = useTranslation();

  const { data, isLoading } = useQuery({
    queryKey: ["client-detail", clientId, dateFrom, dateTo],
    queryFn: () => getClientDetail(clientId!, { date_from: dateFrom, date_to: dateTo }).then(r => r.data),
    enabled: !!clientId,
  });

  const payStatusColor = (s: string) => {
    if (s === "paid") return "success";
    if (s === "partial") return "warning";
    return "default";
  };

  const payStatusLabel = (s: string) => {
    const map: Record<string, string> = { paid: t("order.payment_status_paid"), partial: t("order.payment_status_partial"), unpaid: t("order.payment_status_unpaid") };
    return map[s] ?? s;
  };

  const columns: ColumnsType<ClientOrderRow> = [
    { title: t("order.number"), dataIndex: "order_number", key: "order_number", width: 130 },
    { title: t("order.date"), dataIndex: "order_date", key: "order_date", width: 100 },
    {
      title: t("report.revenue"),
      dataIndex: "total_sale_cny",
      key: "total_sale_cny",
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
      title: t("payment.paid"),
      dataIndex: "paid_cny",
      key: "paid_cny",
      align: "right",
      render: (v) => fmtCny(v),
    },
    {
      title: t("report.payment_status"),
      dataIndex: "payment_status",
      key: "payment_status",
      align: "center",
      render: (v) => <Tag color={payStatusColor(v)}>{payStatusLabel(v)}</Tag>,
    },
    {
      title: t("report.remaining"),
      dataIndex: "remaining",
      key: "remaining",
      align: "right",
      render: (v) => (
        <Text style={{ color: Number(v) > 0 ? "#cf1322" : undefined }}>{fmtCny(v)}</Text>
      ),
    },
    {
      title: t("report.net_profit"),
      dataIndex: "profit",
      key: "profit",
      align: "right",
      render: (v) => (
        <Text style={{ color: Number(v) >= 0 ? "#389e0d" : "#cf1322" }}>{fmtCny(v)}</Text>
      ),
    },
  ];

  const balance = Number(data?.balance ?? 0);
  const balanceColor = balance >= 0 ? "#389e0d" : "#cf1322";
  const balanceLabel = balance >= 0
    ? t("report.overpayment")
    : t("report.debt");

  return (
    <Drawer
      title={clientName}
      open={!!clientId}
      onClose={onClose}
      width="min(900px, 98vw)"
      styles={{ body: { padding: "16px", overflowX: "auto" } }}
    >
      {isLoading ? (
        <Spin />
      ) : data ? (
        <>
          <Descriptions
            bordered
            size="small"
            column={{ xs: 1, sm: 2, md: 3 }}
            style={{ marginBottom: 20 }}
          >
            <Descriptions.Item label={t("report.revenue")}>{fmtCny(data.total_revenue)}</Descriptions.Item>
            <Descriptions.Item label={t("report.cogs")}>{fmtCny(data.total_cogs)}</Descriptions.Item>
            <Descriptions.Item label={t("report.direct_expenses")}>{fmtCny(data.total_direct_expenses)}</Descriptions.Item>
            <Descriptions.Item label={t("report.client_expenses")}>
              <Text style={{ color: Number(data.client_expenses) > 0 ? "#fa8c16" : undefined }}>
                {fmtCny(data.client_expenses)}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label={t("report.net_profit")}>
              <Text strong style={{ color: Number(data.total_profit) >= 0 ? "#389e0d" : "#cf1322" }}>
                {fmtCny(data.total_profit)}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label={balanceLabel}>
              <Text strong style={{ color: balanceColor }}>
                {fmtCny(Math.abs(balance))}
              </Text>
            </Descriptions.Item>
            {Number(data?.unallocated_cny ?? 0) > 0 && (
              <Descriptions.Item label={t("payment.unallocated")}>
                <Text strong style={{ color: "#faad14" }}>
                  {fmtCny(Number(data!.unallocated_cny))}
                </Text>
              </Descriptions.Item>
            )}
          </Descriptions>

          <div style={{ overflowX: "auto" }}>
            <Table
              dataSource={data.orders}
              columns={columns}
              rowKey="order_id"
              pagination={false}
              size="small"
              scroll={{ x: 800 }}
            />
          </div>
        </>
      ) : null}
    </Drawer>
  );
}
