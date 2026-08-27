import { useState } from "react";
import { Button, Space, Typography, Row, Col, DatePicker, Select, Input, Tag, Tooltip, Modal, Segmented } from "antd";
import TopScrollTable from "../common/TopScrollTable";
import { useIsMobile } from "../../hooks/useIsMobile";
import { EyeOutlined, EditOutlined, DeleteOutlined, CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import type { OrderListItem } from "../../types/order";
import { getOrders, cancelOrder } from "../../api/orders";
import { getManagers, getBusinessTypes } from "../../api/references";
import CounterpartySelect from "../common/CounterpartySelect";
import { OrderStatusTag, PaymentStatusTag, BusinessTypeTag } from "./OrderStatusTag";
import { useHasAnyRole } from "../../hooks/useRole";

const { Text } = Typography;

const fmtCny = (v: number) => v?.toLocaleString("ru-RU", { minimumFractionDigits: 2 });

export default function OrderTable() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const canSeeCost = useHasAnyRole("purchaser", "accountant", "admin");
  const canSeeMargin = useHasAnyRole("accountant", "admin");

  const [cancelModal, setCancelModal] = useState<{ open: boolean; orderId: string | null }>({ open: false, orderId: null });
  const [cancelReason, setCancelReason] = useState("");

  const [searchParams, setSearchParams] = useSearchParams();

  const search = searchParams.get("q") ?? "";
  const clientId = searchParams.get("client") ?? undefined;
  const btId = searchParams.get("bt") ?? undefined;
  const statusFilter = searchParams.get("status") ?? undefined;
  const syncStatusFilter = searchParams.get("sync") ?? undefined;
  const sourceFilter = searchParams.get("source") ?? "all";
  const managerId = searchParams.get("manager") ?? undefined;
  const dateFrom = searchParams.get("from");
  const dateTo = searchParams.get("to");
  const dateRange: [string, string] | null = dateFrom && dateTo ? [dateFrom, dateTo] : null;
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

  const params = {
    search: search || undefined, client_id: clientId, business_type_id: btId,
    status: statusFilter, manager_id: managerId,
    date_from: dateRange?.[0], date_to: dateRange?.[1],
    sync_status: syncStatusFilter,
    source: sourceFilter === "all" ? undefined : sourceFilter,
    page, page_size: 20,
  };

  const { data, isLoading } = useQuery({
    queryKey: ["orders", params],
    queryFn: () => getOrders(params).then(r => r.data),
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
      fixed: "left" as const,
      ellipsis: true,
      render: (num, row) => (
        <Tooltip title={num} placement="topLeft">
          <Space size={4}>
            <Button type="link" style={{ padding: 0, maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "inline-block" }}
              onClick={() => navigate(`/orders/${row.id}`)}>
              {num}
            </Button>
            {row.source === "net" && (
              <Tag color="geekblue" style={{ fontSize: 10, padding: "0 4px", lineHeight: "16px", borderRadius: 3, margin: 0 }}>NET</Tag>
            )}
            {row.excluded_from_accounting && (
              <Tooltip title={t("order.excluded_from_accounting")}>
                <Tag color="default" style={{ fontSize: 10, padding: "0 4px", lineHeight: "16px", borderRadius: 3 }}>∅</Tag>
              </Tooltip>
            )}
          </Space>
        </Tooltip>
      ),
    },
    { title: t("order.date"), dataIndex: "order_date", key: "order_date", width: 100 },
    {
      title: t("order.client"),
      key: "client",
      width: 80,
      render: (_: any, row: OrderListItem) => row.client_code
        ? <Tooltip title={row.client_name}><span style={{ fontWeight: 600 }}>{row.client_code}</span></Tooltip>
        : <span style={{ fontSize: 11, color: "#999" }}>{row.client_name}</span>,
    },
    {
      title: t("order.business_type"),
      key: "bt",
      width: 120,
      render: (_, row) => <BusinessTypeTag code={row.business_type_code} name={row.business_type_name} nameCn={row.business_type_name_cn} />,
    },
    ...((sourceFilter === "net" || (data?.items ?? []).some(o => o.source === "net")) ? [{
      title: t("order.cargo_status"),
      key: "cargo_status",
      width: 180,
      render: (_: any, row: OrderListItem) => row.source === "net" && row.cargo_status_label
        ? (
          <Space direction="vertical" size={0}>
            <Tag color="cyan" style={{ margin: 0 }}>{row.cargo_status_label}</Tag>
            {row.cargo_status_at && (
              <Text type="secondary" style={{ fontSize: 11 }}>{dayjs(row.cargo_status_at).format("DD.MM HH:mm")}</Text>
            )}
          </Space>
        )
        : <Text type="secondary">—</Text>,
    }] : []),
    { title: t("order.manager"), dataIndex: "manager_name", key: "manager_name", width: 130 },
    {
      title: `${t("order.total_sale")} (CNY)`,
      key: "sale",
      width: 130,
      align: "right",
      render: (_, row) => <Text>{fmtCny(row.total_sale_cny)}</Text>,
    },
    ...(canSeeCost ? [{
      title: `${t("order.total_cost")} (CNY)`,
      key: "cost",
      width: 130,
      align: "right" as const,
      render: (_: any, row: OrderListItem) => <Text type="secondary">{fmtCny(row.total_cost_cny ?? 0)}</Text>,
    }] : []),
    ...(canSeeMargin ? [{
      title: `${t("order.margin")} (CNY)`,
      key: "margin",
      width: 120,
      align: "right" as const,
      render: (_: any, row: OrderListItem) => {
        const m = row.total_sale_cny - (row.total_cost_cny ?? 0);
        return <Text type={m >= 0 ? "success" : "danger"}>{fmtCny(m)}</Text>;
      },
    }] : []),
    {
      title: t("order.paid_amount"),
      key: "paid",
      width: 120,
      align: "right",
      render: (_, row) => <Text>{fmtCny(row.paid_amount_cny)}</Text>,
    },
    {
      title: t("order.remaining_amount"),
      key: "remaining",
      width: 120,
      align: "right",
      render: (_, row) => (
        <Text type={row.remaining_amount_cny > 0 ? "danger" : "success"}>
          {fmtCny(row.remaining_amount_cny)}
        </Text>
      ),
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
      title: "",
      key: "sync_status",
      width: 28,
      render: (_, row) => {
        if (row.business_type_code !== "logistics") return null;
        if (!row.sync_status) return <Tooltip title={t("order.sync.not_synced")}><MinusCircleOutlined style={{ color: "#d9d9d9" }} /></Tooltip>;
        if (row.sync_status === "synced") return <Tooltip title={t("order.sync.synced")}><CheckCircleOutlined style={{ color: "#52c41a" }} /></Tooltip>;
        if (row.sync_status === "failed") return <Tooltip title={t("order.sync.failed")}><CloseCircleOutlined style={{ color: "#ff4d4f" }} /></Tooltip>;
        if (row.sync_status === "disabled") return <Tooltip title={t("order.sync.disabled")}><MinusCircleOutlined style={{ color: "#bfbfbf" }} /></Tooltip>;
        return <Tag style={{ fontSize: 10 }}>{row.sync_status}</Tag>;
      },
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 100,
      render: (_, row) => (
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => navigate(`/orders/${row.id}`)} />
          <Button icon={<EditOutlined />} size="small" onClick={() => navigate(`/orders/${row.id}/edit`)} />
          <Button
            icon={<DeleteOutlined />}
            size="small"
            danger
            onClick={() => { setCancelReason(""); setCancelModal({ open: true, orderId: row.id }); }}
          />
        </Space>
      ),
    },
  ];

  const btOptions = (businessTypes || []).map(bt => ({ value: bt.id, label: i18n.language === "zh" && bt.name_cn ? bt.name_cn : bt.name }));
  const managerOptions = (managers || []).map(m => ({ value: m.id, label: m.full_name }));
  const statusOptions = ["new", "active", "closed", "cancelled"].map(s => ({ value: s, label: t(`order.status_${s}`) }));

  const isMobile = useIsMobile();
  const totalSale = data?.page_total_sale_cny ?? 0;
  const totalCost = data?.page_total_cost_cny ?? 0;

  const handleCancelConfirm = () => {
    if (!cancelModal.orderId || !cancelReason.trim()) return;
    cancelMutation.mutate({ id: cancelModal.orderId, reason: cancelReason.trim() });
    setCancelModal({ open: false, orderId: null });
  };

  return (
    <div>
      <Modal
        open={cancelModal.open}
        title={t("order.cancel_modal_title")}
        onOk={handleCancelConfirm}
        onCancel={() => setCancelModal({ open: false, orderId: null })}
        okText={t("order.cancel_btn")}
        cancelText={t("common.cancel")}
        okButtonProps={{ danger: true, disabled: !cancelReason.trim(), loading: cancelMutation.isPending }}
        destroyOnClose
      >
        <p style={{ marginBottom: 8 }}>{t("order.cancel_reason_label")}:</p>
        <Input.TextArea
          rows={3}
          placeholder={t("order.cancel_reason_placeholder")}
          value={cancelReason}
          onChange={e => setCancelReason(e.target.value)}
          autoFocus
        />
      </Modal>
      <Row gutter={[8, 8]} style={{ marginBottom: 12 }} className="mobile-full-width">
        <Col xs={24} sm="auto">
          <Segmented
            block={isMobile}
            value={sourceFilter}
            onChange={(v) => setFilter({ source: v === "all" ? null : String(v) })}
            options={[
              { label: t("order.source_all"), value: "all" },
              { label: t("order.source_erp"), value: "erp" },
              { label: "NET", value: "net" },
            ]}
          />
        </Col>
        <Col xs={24} sm="auto">
          <Input.Search placeholder={t("order.number")} allowClear style={{ width: isMobile ? "100%" : 180 }}
            defaultValue={search}
            onSearch={v => setFilter({ q: v || null })}
            onChange={e => { if (!e.target.value) setFilter({ q: null }); }}
          />
        </Col>
        <Col xs={24} sm="auto">
          <DatePicker.RangePicker style={{ width: isMobile ? "100%" : 240 }}
            value={dateRange ? [dayjs(dateRange[0]), dayjs(dateRange[1])] : undefined}
            onChange={(_, strs) => setFilter({ from: strs[0] || null, to: strs[1] || null })}
          />
        </Col>
        <Col xs={24} sm="auto">
          <CounterpartySelect
            type="client"
            placeholder={t("order.client")}
            style={{ width: isMobile ? "100%" : 180 }}
            allowClear
            value={clientId}
            onChange={v => setFilter({ client: v ?? null })}
          />
        </Col>
        {!isMobile && (
          <>
            <Col>
              <Select allowClear placeholder={t("order.business_type")} style={{ width: 140 }} options={btOptions}
                value={btId}
                onChange={v => setFilter({ bt: v ?? null })} />
            </Col>
            <Col>
              <Select allowClear placeholder={t("order.title")} style={{ width: 130 }} options={statusOptions}
                value={statusFilter}
                onChange={v => setFilter({ status: v ?? null })} />
            </Col>
            <Col>
              <Select allowClear placeholder={t("order.manager")} style={{ width: 150 }} options={managerOptions}
                value={managerId}
                onChange={v => setFilter({ manager: v ?? null })} />
            </Col>
            <Col>
              <Select
                allowClear
                placeholder={t("order.sync.title")}
                style={{ width: 130 }}
                value={syncStatusFilter}
                options={["synced", "failed", "disabled"].map(s => ({ value: s, label: t(`order.sync.${s}`) }))}
                onChange={v => setFilter({ sync: v ?? null })}
              />
            </Col>
          </>
        )}
        <Col xs={24} sm="auto" style={{ textAlign: isMobile ? "left" : "right", flex: isMobile ? undefined : "auto" }}>
          <Button type="primary" block={isMobile} onClick={() => navigate("/orders/new")}>{t("order.create_new")}</Button>
        </Col>
      </Row>

      <TopScrollTable
        columns={columns} dataSource={data?.items ?? []} rowKey="id" loading={isLoading} size="small"
        scroll={{ x: "max-content" }}
        pagination={{ current: page, total: data?.total ?? 0, pageSize: 20, onChange: handlePageChange, showTotal: t => `${t}`, size: isMobile ? "small" : "default" }}
        footer={() => (
          <Row justify="end" gutter={24}>
            <Col><Text type="secondary">{t("order.page_totals")}:</Text></Col>
            <Col><Text strong>{t("order.total_sale")}: {fmtCny(totalSale)} CNY</Text></Col>
            {canSeeCost && (
              <Col><Text>{t("order.total_cost")}: {fmtCny(totalCost)} CNY</Text></Col>
            )}
            {canSeeMargin && (
              <Col><Text type={totalSale - totalCost >= 0 ? "success" : "danger"}>{t("order.margin")}: {fmtCny(totalSale - totalCost)} CNY</Text></Col>
            )}
          </Row>
        )}
      />
    </div>
  );
}
