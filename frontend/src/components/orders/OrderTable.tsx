import { useState } from "react";
import { Table, Button, Space, Popconfirm, Typography, Row, Col, DatePicker, Select, Input } from "antd";
import { EyeOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import type { OrderListItem } from "../../types/order";
import { getOrders, cancelOrder } from "../../api/orders";
import { getCounterparties } from "../../api/counterparties";
import { getManagers, getBusinessTypes } from "../../api/references";
import { OrderStatusTag, PaymentStatusTag, BusinessTypeTag } from "./OrderStatusTag";

const { Text } = Typography;

const fmtCny = (v: number) => v?.toLocaleString("ru-RU", { minimumFractionDigits: 2 });

export default function OrderTable() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [clientId, setClientId] = useState<string | undefined>();
  const [btId, setBtId] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [managerId, setManagerId] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [page, setPage] = useState(1);

  const params = {
    search: search || undefined, client_id: clientId, business_type_id: btId,
    status: statusFilter, manager_id: managerId,
    date_from: dateRange?.[0], date_to: dateRange?.[1],
    page, page_size: 20,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["orders", params],
    queryFn: () => getOrders(params).then(r => r.data),
  });

  const { data: clients } = useQuery({
    queryKey: ["counterparties-clients"],
    queryFn: () => getCounterparties({ type: "client", page_size: 200 }).then(r => r.data),
  });

  const { data: managers } = useQuery({
    queryKey: ["managers"],
    queryFn: () => getManagers().then(r => r.data),
  });

  const { data: businessTypes } = useQuery({
    queryKey: ["business-types"],
    queryFn: () => getBusinessTypes().then(r => r.data),
  });

  const cancelMutation = useMutation({
    mutationFn: cancelOrder,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });

  const columns: ColumnsType<OrderListItem> = [
    {
      title: t("order.number"),
      dataIndex: "order_number",
      key: "order_number",
      width: 160,
      render: (num, row) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => navigate(`/orders/${row.id}`)}>
          {num}
        </Button>
      ),
    },
    { title: t("order.date"), dataIndex: "order_date", key: "order_date", width: 110 },
    { title: t("order.client"), dataIndex: "client_name", key: "client_name" },
    {
      title: t("order.business_type"),
      key: "bt",
      width: 120,
      render: (_, row) => <BusinessTypeTag code={row.business_type_code} name={row.business_type_name} />,
    },
    { title: t("order.manager"), dataIndex: "manager_name", key: "manager_name", width: 130 },
    {
      title: `${t("order.total_sale")} (CNY)`,
      key: "sale",
      width: 130,
      align: "right",
      render: (_, row) => <Text>{fmtCny(row.total_sale_cny)}</Text>,
    },
    {
      title: `${t("order.total_cost")} (CNY)`,
      key: "cost",
      width: 130,
      align: "right",
      render: (_, row) => <Text type="secondary">{fmtCny(row.total_cost_cny)}</Text>,
    },
    {
      title: `${t("order.margin")} (CNY)`,
      key: "margin",
      width: 120,
      align: "right",
      render: (_, row) => {
        const m = row.total_sale_cny - row.total_cost_cny;
        return <Text type={m >= 0 ? "success" : "danger"}>{fmtCny(m)}</Text>;
      },
    },
    {
      title: t("order.title").slice(0, 6),
      key: "status",
      width: 100,
      render: (_, row) => <OrderStatusTag status={row.status} />,
    },
    {
      title: t("order.payment_status_unpaid").slice(0, 6),
      key: "payment",
      width: 100,
      render: (_, row) => <PaymentStatusTag status={row.payment_status} />,
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 100,
      render: (_, row) => (
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => navigate(`/orders/${row.id}`)} />
          <Button icon={<EditOutlined />} size="small" onClick={() => navigate(`/orders/${row.id}/edit`)} />
          <Popconfirm title={t("order.cancel_confirm")} onConfirm={() => cancelMutation.mutate(row.id)} okText={t("common.yes")} cancelText={t("common.no")}>
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const btOptions = (businessTypes || []).map(bt => ({ value: bt.id, label: bt.name }));
  const clientOptions = (clients?.items || []).map(c => ({ value: c.id, label: c.name }));
  const managerOptions = (managers || []).map(m => ({ value: m.id, label: m.full_name }));
  const statusOptions = ["new", "active", "closed", "cancelled"].map(s => ({ value: s, label: t(`order.status_${s}`) }));

  const totalSale = data?.page_total_sale_cny ?? 0;
  const totalCost = data?.page_total_cost_cny ?? 0;

  return (
    <div>
      <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
        <Col>
          <Input.Search placeholder={t("order.number")} allowClear style={{ width: 180 }}
            onSearch={v => { setSearch(v); setPage(1); }}
            onChange={e => { if (!e.target.value) { setSearch(""); setPage(1); } }}
          />
        </Col>
        <Col>
          <DatePicker.RangePicker style={{ width: 240 }}
            onChange={(_, strs) => { setDateRange(strs[0] && strs[1] ? [strs[0], strs[1]] : null); setPage(1); }}
          />
        </Col>
        <Col>
          <Select allowClear placeholder={t("order.client")} style={{ width: 180 }} options={clientOptions}
            showSearch filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())}
            onChange={v => { setClientId(v); setPage(1); }} />
        </Col>
        <Col>
          <Select allowClear placeholder={t("order.business_type")} style={{ width: 140 }} options={btOptions}
            onChange={v => { setBtId(v); setPage(1); }} />
        </Col>
        <Col>
          <Select allowClear placeholder={t("order.title")} style={{ width: 130 }} options={statusOptions}
            onChange={v => { setStatusFilter(v); setPage(1); }} />
        </Col>
        <Col>
          <Select allowClear placeholder={t("order.manager")} style={{ width: 150 }} options={managerOptions}
            onChange={v => { setManagerId(v); setPage(1); }} />
        </Col>
        <Col flex="auto" style={{ textAlign: "right" }}>
          <Button type="primary" onClick={() => navigate("/orders/new")}>{t("order.create_new")}</Button>
        </Col>
      </Row>

      <Table
        columns={columns} dataSource={data?.items ?? []} rowKey="id" loading={isLoading} size="small"
        pagination={{ current: page, total: data?.total ?? 0, pageSize: 20, onChange: setPage, showTotal: t => `${t}` }}
        footer={() => (
          <Row justify="end" gutter={24}>
            <Col><Text type="secondary">{t("order.page_totals")}:</Text></Col>
            <Col><Text strong>{t("order.total_sale")}: {fmtCny(totalSale)} CNY</Text></Col>
            <Col><Text>{t("order.total_cost")}: {fmtCny(totalCost)} CNY</Text></Col>
            <Col><Text type={totalSale - totalCost >= 0 ? "success" : "danger"}>{t("order.margin")}: {fmtCny(totalSale - totalCost)} CNY</Text></Col>
          </Row>
        )}
      />
    </div>
  );
}
