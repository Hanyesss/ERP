import { useNavigate, useSearchParams } from "react-router-dom";
import { Table, Button, Input, Select, Tag, Row, Col, Typography, Space, Tooltip } from "antd";
import TopScrollTable from "../components/common/TopScrollTable";
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
  const [searchParams, setSearchParams] = useSearchParams();

  const search = searchParams.get("q") ?? "";
  const supplierId = searchParams.get("supplier") ?? undefined;
  const paymentStatus = searchParams.get("status") ?? undefined;
  const page = Number(searchParams.get("page") ?? "1");

  const setFilter = (updates: Record<string, string | undefined | null>) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(updates)) {
        if (v != null && v !== "") next.set(k, v); else next.delete(k);
      }
      next.set("page", "1");
      return next;
    }, { replace: true });
  };

  const handlePageChange = (p: number) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.set("page", String(p));
      return next;
    }, { replace: true });
  };

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
      fixed: "left" as const,
      width: 160,
      ellipsis: true,
      render: (num, row) => (
        <Tooltip title={num} placement="topLeft">
          <Space size={4}>
            <Button type="link" size="small"
              style={{ maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "inline-block" }}
              onClick={() => navigate(`/purchases/${row.id}`)}>
              {num}
            </Button>
            {row.excluded_from_accounting && (
              <Tooltip title={t("order.excluded_from_accounting")}>
                <Tag color="default" style={{ fontSize: 10, padding: "0 4px", lineHeight: "16px", borderRadius: 3 }}>∅</Tag>
              </Tooltip>
            )}
          </Space>
        </Tooltip>
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
      width: 180,
      ellipsis: { showTitle: true },
    },
    {
      title: t("order.title"),
      dataIndex: "order_number",
      key: "order_number",
      width: 160,
      ellipsis: { showTitle: true },
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
            defaultValue={search}
            style={{ width: 220 }}
            onSearch={val => setFilter({ q: val || null })}
            onChange={e => { if (!e.target.value) setFilter({ q: null }); }}
          />
        </Col>
        <Col>
          <CounterpartySelect
            type="supplier"
            placeholder={t("purchase.supplier")}
            style={{ width: 200 }}
            allowClear
            value={supplierId}
            onChange={v => setFilter({ supplier: v ?? null })}
          />
        </Col>
        <Col>
          <Select
            allowClear
            placeholder={t("purchase.payment_status")}
            style={{ width: 160 }}
            value={paymentStatus}
            options={[
              { value: "unpaid", label: t("purchase.status_unpaid") },
              { value: "partial", label: t("purchase.status_partial") },
              { value: "paid", label: t("purchase.status_paid") },
            ]}
            onChange={v => setFilter({ status: v ?? null })}
          />
        </Col>
      </Row>

      <TopScrollTable scroll={{ x: "max-content" }}
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          total: data?.total ?? 0,
          pageSize: 20,
          onChange: handlePageChange,
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
