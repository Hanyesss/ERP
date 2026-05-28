import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Table, Button, Input, Select, Tag, Row, Col, Typography, Space } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import { getPurchases } from "../api/purchases";
import type { PurchaseListItem } from "../types/purchase";
import CounterpartySelect from "../components/common/CounterpartySelect";

const { Title } = Typography;

const STATUS_COLORS: Record<string, string> = {
  unpaid: "red",
  partial: "orange",
  paid: "green",
};

const fmtCny = (v: number) =>
  v.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PurchasesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [supplierId, setSupplierId] = useState<string | undefined>();
  const [paymentStatus, setPaymentStatus] = useState<string | undefined>();
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["purchases", search, supplierId, paymentStatus, page],
    queryFn: () => getPurchases({
      search: search || undefined,
      supplier_id: supplierId,
      payment_status: paymentStatus,
      page, page_size: 20,
    }).then(r => r.data),
  });

  const columns: ColumnsType<PurchaseListItem> = [
    {
      title: t("purchase.number"),
      dataIndex: "purchase_number",
      key: "number",
      render: (num, row) => (
        <Button type="link" size="small" onClick={() => navigate(`/purchases/${row.id}`)}>
          {num}
        </Button>
      ),
    },
    {
      title: t("purchase.date"),
      dataIndex: "purchase_date",
      key: "date",
    },
    {
      title: t("purchase.supplier"),
      dataIndex: "supplier_name",
      key: "supplier",
    },
    {
      title: t("order.title"),
      dataIndex: "order_number",
      key: "order_number",
      render: (num: string | undefined, row) => num
        ? <Button type="link" size="small" onClick={() => navigate(`/orders/${row.order_id}`)}>{num}</Button>
        : "—",
    },
    {
      title: t("purchase.items_count"),
      dataIndex: "items_count",
      key: "items_count",
      align: "right",
    },
    {
      title: t("purchase.total"),
      key: "total",
      align: "right",
      render: (_, row) => `${fmtCny(row.total_amount)} ${row.currency}`,
    },
    {
      title: `${t("purchase.total")} CNY`,
      dataIndex: "total_amount_cny",
      key: "total_cny",
      align: "right",
      render: v => fmtCny(v),
    },
    {
      title: t("purchase.paid_amount"),
      dataIndex: "paid_amount_cny",
      key: "paid_cny",
      align: "right",
      render: (v: number) => <span style={{ color: "#666" }}>{fmtCny(v)}</span>,
    },
    {
      title: t("purchase.remaining_amount"),
      dataIndex: "remaining_amount_cny",
      key: "remaining_cny",
      align: "right",
      render: (v: number) => (
        <span style={{ color: v > 0 ? "#cf1322" : "#3f8600" }}>{fmtCny(v)}</span>
      ),
    },
    {
      title: t("purchase.payment_status"),
      dataIndex: "payment_status",
      key: "status",
      render: (s: string) => (
        <Tag color={STATUS_COLORS[s]}>{t(`purchase.status_${s}`)}</Tag>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("purchase.title")}</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/purchases/new")}>
            {t("purchase.add_new")}
          </Button>
        </Col>
      </Row>

      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col>
          <Input.Search
            placeholder={t("purchase.search_placeholder")}
            allowClear
            style={{ width: 220 }}
            onSearch={val => { setSearch(val); setPage(1); }}
            onChange={e => { if (!e.target.value) { setSearch(""); setPage(1); } }}
          />
        </Col>
        <Col>
          <CounterpartySelect
            type="supplier"
            placeholder={t("purchase.supplier")}
            style={{ width: 200 }}
            allowClear
            onChange={v => { setSupplierId(v); setPage(1); }}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("purchase.payment_status")}
            style={{ width: 160 }}
            options={[
              { value: "unpaid", label: t("purchase.status_unpaid") },
              { value: "partial", label: t("purchase.status_partial") },
              { value: "paid", label: t("purchase.status_paid") },
            ]}
            onChange={v => { setPaymentStatus(v); setPage(1); }}
          />
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          total: data?.total ?? 0,
          pageSize: 20,
          onChange: setPage,
          showTotal: total => `${total}`,
        }}
        summary={() => data?.page_total_cny ? (
          <Table.Summary.Row>
            <Table.Summary.Cell index={0} colSpan={5} align="right">
              <strong>{t("purchase.total")} CNY:</strong>
            </Table.Summary.Cell>
            <Table.Summary.Cell index={5} align="right">
              <strong>{fmtCny(data.page_total_cny)}</strong>
            </Table.Summary.Cell>
            <Table.Summary.Cell index={6} />
            <Table.Summary.Cell index={7} />
            <Table.Summary.Cell index={8} />
          </Table.Summary.Row>
        ) : undefined}
      />
    </div>
  );
}
