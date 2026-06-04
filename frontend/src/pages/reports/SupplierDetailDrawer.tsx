import { Drawer, Table, Typography, Descriptions, Spin, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getSupplierDetail, type SupplierPurchaseRow } from "../../api/reports";
import type { ColumnsType } from "antd/es/table";

const { Text } = Typography;

const fmtCny = (v: number | string | null | undefined) =>
  Number(v ?? 0).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props {
  supplierId: string | null;
  supplierName: string;
  dateFrom: string;
  dateTo: string;
  onClose: () => void;
}

export default function SupplierDetailDrawer({ supplierId, supplierName, dateFrom, dateTo, onClose }: Props) {
  const { t } = useTranslation();

  const { data, isLoading } = useQuery({
    queryKey: ["supplier-detail", supplierId, dateFrom, dateTo],
    queryFn: () => getSupplierDetail(supplierId!, { date_from: dateFrom, date_to: dateTo }).then(r => r.data),
    enabled: !!supplierId,
  });

  const payStatusColor = (s: string) => {
    if (s === "paid") return "success";
    if (s === "partial") return "warning";
    return "default";
  };

  const payStatusLabel = (s: string) => {
    const map: Record<string, string> = { paid: t("payment.status_paid"), partial: t("payment.status_partial"), unpaid: t("payment.status_unpaid") };
    return map[s] ?? s;
  };

  const columns: ColumnsType<SupplierPurchaseRow> = [
    { title: t("purchase.number"), dataIndex: "purchase_number", key: "purchase_number", width: 140 },
    { title: t("purchase.date"), dataIndex: "purchase_date", key: "purchase_date", width: 100 },
    {
      title: t("order.number"),
      dataIndex: "order_number",
      key: "order_number",
      width: 130,
      render: (v) => v ?? "—",
    },
    {
      title: t("report.order_sale"),
      dataIndex: "order_sale_cny",
      key: "order_sale_cny",
      align: "right",
      render: (v) => v != null ? fmtCny(v) : "—",
    },
    {
      title: t("report.purchase_amount"),
      dataIndex: "total_amount_cny",
      key: "total_amount_cny",
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
  ];

  const balance = Number(data?.balance ?? 0);
  const balanceColor = balance >= 0 ? "#389e0d" : "#cf1322";
  const balanceLabel = balance >= 0
    ? t("report.overpayment")
    : t("report.debt_to_supplier");

  return (
    <Drawer
      title={supplierName}
      open={!!supplierId}
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
            <Descriptions.Item label={t("report.purchase_amount")}>{fmtCny(data.total_purchased_cny)}</Descriptions.Item>
            <Descriptions.Item label={t("payment.paid")}>{fmtCny(data.total_paid_cny)}</Descriptions.Item>
            <Descriptions.Item label={balanceLabel}>
              <Text strong style={{ color: balanceColor }}>
                {fmtCny(Math.abs(balance))}
              </Text>
            </Descriptions.Item>
          </Descriptions>

          <div style={{ overflowX: "auto" }}>
            <Table
              dataSource={data.purchases}
              columns={columns}
              rowKey="purchase_id"
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
