import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button, Card, Col, Descriptions, Divider, Form, Image, Input, Modal, Popconfirm, Row, Select,
  Space, Statistic, Table, Tabs, Tag, Timeline, Typography, message,
} from "antd";
import { EditOutlined, CheckOutlined, CloseOutlined, ShoppingCartOutlined, DownloadOutlined, SyncOutlined, LinkOutlined, PlusOutlined, FileOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { getOrder, closeOrder, cancelOrder, getOrderHistory, downloadClientPdf, downloadLogisticsPdf, getItemPhotoUrl } from "../api/orders";
import { getPurchases } from "../api/purchases";
import { getPaymentsForOrder } from "../api/payments";
import { getExpenses, getFileUrl } from "../api/expenses";
import { syncOrderToSite, pushOrderStatus } from "../api/integration";
import { OrderStatusTag, PaymentStatusTag, BusinessTypeTag } from "../components/orders/OrderStatusTag";
import OrderFilesTab from "../components/orders/OrderFilesTab";
import { useHasAnyRole } from "../hooks/useRole";
import type { OrderItem, OrderCharge } from "../types/order";
import type { ExpenseListItem } from "../types/expense";

const { Title, Text } = Typography;

const fmtCny = (v: number | null | undefined) =>
  v != null ? v.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

const CHARGE_TYPE_ORDER = ["delivery", "insurance_percent", "insurance_cost", "china_delivery", "extra_packing", "loaders"];

export default function OrderDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const canSeeCost = useHasAnyRole("purchaser", "accountant", "admin");
  const canDownloadPdf = useHasAnyRole("seller", "purchaser", "employee", "manager", "accountant", "admin");
  const canSync = useHasAnyRole("seller", "purchaser", "employee", "manager", "accountant", "admin");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [logisticsPdfLoading, setLogisticsPdfLoading] = useState(false);
  const [cancelModal, setCancelModal] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [pushStatusOpen, setPushStatusOpen] = useState(false);
  const [pushStatusForm] = Form.useForm();

  const { data: order, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: () => getOrder(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: history } = useQuery({
    queryKey: ["order-history", id],
    queryFn: () => getOrderHistory(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: purchasesData } = useQuery({
    queryKey: ["purchases-for-order", id],
    queryFn: () => getPurchases({ order_id: id!, page_size: 100 }).then(r => r.data),
    enabled: !!id && canSeeCost,
  });

  const { data: orderPayments } = useQuery({
    queryKey: ["payments-for-order", id],
    queryFn: () => getPaymentsForOrder(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: orderExpenses } = useQuery({
    queryKey: ["expenses-for-order", id],
    queryFn: () => getExpenses({ order_id: id!, page_size: 100 }).then(r => r.data),
    enabled: !!id,
  });

  const closeMutation = useMutation({
    mutationFn: () => closeOrder(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      message.success(t("order.status_closed") + " ✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const cancelMutation = useMutation({
    mutationFn: (reason: string) => cancelOrder({ id: id!, reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      message.success(t("order.status_cancelled") + " ✓");
      setCancelModal(false);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const syncMutation = useMutation({
    mutationFn: () => syncOrderToSite(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order", id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      message.success(t("order.sync.synced") + " ✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const pushStatusMutation = useMutation({
    mutationFn: (vals: { status: string; comment?: string }) =>
      pushOrderStatus(id!, vals.status, vals.comment),
    onSuccess: () => {
      setPushStatusOpen(false);
      pushStatusForm.resetFields();
      message.success(t("order.sync.status_pushed") + " ✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleDownloadPdf = async () => {
    setPdfLoading(true);
    try {
      const res = await downloadClientPdf(id!);
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `quotation_${order?.order_number || id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      message.error(e.response?.data?.detail || "PDF generation failed");
    } finally {
      setPdfLoading(false);
    }
  };

  const handleDownloadLogisticsPdf = async () => {
    setLogisticsPdfLoading(true);
    try {
      const res = await downloadLogisticsPdf(id!);
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `waybill_${order?.order_number || id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      message.error(e.response?.data?.detail || "PDF generation failed");
    } finally {
      setLogisticsPdfLoading(false);
    }
  };

  if (isLoading || !order) return null;

  const isLogistics = order.business_type_code === "logistics";
  const expensesCny = order.expenses_cny ?? 0;
  const totalCostCny = order.total_cost_cny ?? 0;
  const margin = canSeeCost
    ? order.total_sale_cny - totalCostCny - expensesCny
    : null;
  const marginPct = margin != null && order.total_sale_cny > 0
    ? (margin / order.total_sale_cny) * 100
    : null;
  const canEdit = order.status === "new" || order.status === "active";
  const canClose = order.status === "new" || order.status === "active";
  const canCancel = order.status !== "cancelled" && order.status !== "closed";

  const chargeRateMap: Record<string, number> = { CNY: 1 };
  (order.charges || []).forEach(c => {
    if (c.amount > 0 && c.rate_to_cny > 0) chargeRateMap[c.currency] = Number(c.rate_to_cny);
  });

  const tradeItemColumns: ColumnsType<OrderItem> = [
    { title: "№", key: "idx", width: 40, render: (_, __, i) => i + 1 },
    { title: t("order.item_name"), dataIndex: "name", key: "name",
      render: (name, row: any) => (
        <div>
          <div>{name}</div>
          {row.name_cn && <div style={{ color: "#888", fontSize: 11 }}>{row.name_cn}</div>}
          {row.model && <div style={{ color: "#555", fontSize: 11 }}>{t("order.model")}: {row.model}</div>}
          {row.specification && (
            <div style={{ color: "#888", fontSize: 11, whiteSpace: "pre-wrap", maxWidth: 200 }}>{row.specification}</div>
          )}
        </div>
      )
    },
    { title: t("order.photos"), key: "photos", width: 120,
      render: (_: any, row: any) => {
        const photos = row.photos || [];
        if (!photos.length) return null;
        return (
          <Image.PreviewGroup>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {photos.map((ph: any) => (
                <Image
                  key={ph.id}
                  src={getItemPhotoUrl(row.id, ph.id)}
                  width={48}
                  height={48}
                  style={{ objectFit: "cover", borderRadius: 4, border: "1px solid #eee" }}
                  preview={{ src: getItemPhotoUrl(row.id, ph.id) }}
                />
              ))}
            </div>
          </Image.PreviewGroup>
        );
      }
    },
    { title: t("order.item_quantity"), dataIndex: "quantity", key: "quantity", width: 90, align: "right",
      render: (v, row) => `${v ?? "—"} ${row.unit || ""}`.trim() },
    { title: t("order.item_preferred_supplier"), dataIndex: "preferred_supplier_name", key: "pref_supplier",
      render: v => v ? <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text> : "—" },
    { title: t("order.item_sale_price"), key: "sale", width: 130, align: "right",
      render: (_, row) => row.sale_price != null ? `${row.sale_price} ${row.sale_currency}` : "—" },
    { title: `${t("order.total_sale")} CNY`, key: "sale_cny", width: 120, align: "right",
      render: (_, row) => row.sale_price != null && row.quantity != null && row.sale_rate_to_cny != null
        ? fmtCny(Number(row.quantity) * Number(row.sale_price) * Number(row.sale_rate_to_cny))
        : "—" },
    ...(canSeeCost ? [
      { title: t("purchase.purchased_qty"), key: "purchased", width: 100, align: "right" as const,
        render: (_: any, row: OrderItem) => {
          const pq = row.purchased_quantity;
          const q = row.quantity;
          if (pq == null || q == null) return "—";
          return (
            <Tag color={Number(pq) >= Number(q) ? "green" : "orange"}>
              {Number(pq)}/{Number(q)}
            </Tag>
          );
        }
      },
    ] : []),
  ];

  const logisticsItemColumns: ColumnsType<OrderItem> = [
    { title: "№", key: "idx", width: 40, render: (_, __, i) => i + 1 },
    { title: t("order.item_name"), dataIndex: "name", key: "name" },
    { title: t("order.weight_kg"), dataIndex: "weight_kg", key: "weight_kg", align: "right",
      render: v => v != null ? `${v} kg` : "—" },
    { title: t("order.volume_m3"), dataIndex: "volume_m3", key: "volume_m3", align: "right",
      render: v => v != null ? `${v} m³` : "—" },
    { title: t("order.density"), dataIndex: "density_kg_m3", key: "density_kg_m3", align: "right",
      render: v => v != null ? `${v} kg/m³` : "—" },
    { title: t("order.price_per_kg"), key: "ppkg", align: "right",
      render: (_, row) => row.price_per_kg != null ? `${row.price_per_kg} ${row.price_per_kg_currency}` : "—" },
    { title: t("order.cargo_value"), key: "cval", align: "right",
      render: (_, row) => row.cargo_value != null ? `${row.cargo_value} ${row.cargo_value_currency}` : "—" },
    { title: t("order.places_count"), dataIndex: "places_count", key: "places_count", align: "right",
      render: v => v ?? "—" },
  ];

  const chargeColumns: ColumnsType<OrderCharge> = [
    { title: t("order.cost_breakdown"),
      render: (_, row) => t(`order.charge_${row.charge_type}`), key: "type" },
    { title: t("common.amount"), key: "amount", align: "right",
      render: (_, row) => `${fmtCny(Number(row.amount))} ${row.currency}` },
    { title: "CNY", dataIndex: "amount_cny", key: "amount_cny", align: "right",
      render: v => fmtCny(Number(v)) },
  ];

  const linkedPurchases = purchasesData?.items || [];

  const tabItems = [
    {
      key: "main",
      label: t("order.tab_main"),
      children: (
        <>
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label={t("order.number")}>{order.order_number}</Descriptions.Item>
            <Descriptions.Item label={t("order.date")}>{order.order_date}</Descriptions.Item>
            <Descriptions.Item label={t("order.client")}>
              {order.client_name}
              {(order as any).client_phone && (
                <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                  📞 {(order as any).client_phone}
                </Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label={t("order.currency")}>{order.client_currency}</Descriptions.Item>
            <Descriptions.Item label={t("order.business_type")}>
              <BusinessTypeTag code={order.business_type_code} name={order.business_type_name} nameCn={order.business_type_name_cn} />
            </Descriptions.Item>
            <Descriptions.Item label={t("order.manager")}>{order.manager_name}</Descriptions.Item>
            <Descriptions.Item label={t("order.title")}>
              <OrderStatusTag status={order.status} />
            </Descriptions.Item>
            <Descriptions.Item label={t("order.payment_status_unpaid")}>
              <PaymentStatusTag status={order.payment_status} />
            </Descriptions.Item>
            {canSeeCost && order.supplier_payment_status && (
              <Descriptions.Item label={t("order.supplier_payment_status")}>
                <PaymentStatusTag status={order.supplier_payment_status} />
              </Descriptions.Item>
            )}
            {order.notes && (
              <Descriptions.Item label={t("order.notes")} span={2}>{order.notes}</Descriptions.Item>
            )}
          </Descriptions>

          {isLogistics && (
            <>
              <Divider>{t("order.routing_info")}</Divider>
              <Descriptions bordered size="small" column={2}>
                {order.recipient && (
                  <Descriptions.Item label={t("order.recipient")}>{order.recipient}</Descriptions.Item>
                )}
                {order.destination && (
                  <Descriptions.Item label={t("order.destination")}>{order.destination}</Descriptions.Item>
                )}
                {order.arrival_date && (
                  <Descriptions.Item label={t("order.arrival_date")}>{order.arrival_date}</Descriptions.Item>
                )}
                {order.tracking_number && (
                  <Descriptions.Item label={t("order.tracking_number")}>{order.tracking_number}</Descriptions.Item>
                )}
              </Descriptions>

              {canSync && (
                <>
                  <Divider>{t("order.sync.title")}</Divider>
                  <Space direction="vertical" style={{ width: "100%" }}>
                    {order.sync_status === "synced" && (
                      <Space wrap>
                        <Tag color="green" icon={<CheckOutlined />}>{t("order.sync.synced")}</Tag>
                        {order.synced_at && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {new Date(order.synced_at).toLocaleString("ru-RU")}
                          </Text>
                        )}
                        {order.external_shipment_number && (
                          <Text>{t("order.sync.shipment_number")}: <Text strong>{order.external_shipment_number}</Text></Text>
                        )}
                      </Space>
                    )}
                    {order.sync_status === "failed" && (
                      <Space direction="vertical">
                        <Tag color="red" icon={<CloseOutlined />}>{t("order.sync.failed")}</Tag>
                        {order.sync_error && <Text type="danger" style={{ fontSize: 12 }}>{order.sync_error}</Text>}
                      </Space>
                    )}
                    {order.sync_status === "disabled" && (
                      <Text type="secondary">{t("order.sync.disabled")}</Text>
                    )}
                    {!order.sync_status && (
                      <Text type="secondary">{t("order.sync.not_synced")}</Text>
                    )}

                    <Space wrap>
                      <Button
                        icon={<SyncOutlined />}
                        loading={syncMutation.isPending}
                        onClick={() => syncMutation.mutate()}
                      >
                        {order.sync_status === "synced" ? t("order.sync.sync_again") : t("order.sync.sync_now")}
                      </Button>

                      {order.sync_status === "synced" && (
                        <>
                          {order.external_invoice_url && (
                            <Button
                              icon={<DownloadOutlined />}
                              href={order.external_invoice_url}
                              target="_blank"
                            >
                              {t("order.sync.download_invoice")}
                            </Button>
                          )}
                          {order.external_tracking_url && (
                            <Button
                              icon={<LinkOutlined />}
                              href={order.external_tracking_url}
                              target="_blank"
                            >
                              {t("order.sync.open_tracking")}
                            </Button>
                          )}
                          <Button onClick={() => setPushStatusOpen(true)}>
                            {t("order.sync.push_status")}
                          </Button>
                        </>
                      )}
                    </Space>
                  </Space>
                </>
              )}
            </>
          )}
        </>
      ),
    },
    {
      key: "items",
      label: t("order.items"),
      children: (
        <>
          <Table scroll={{ x: "max-content" }}
            columns={isLogistics ? logisticsItemColumns : tradeItemColumns}
            dataSource={order.items}
            rowKey="id"
            size="small"
            pagination={false}
          />

          {isLogistics && order.charges.length > 0 && (
            <>
              <Divider>{t("order.cost_breakdown")}</Divider>
              <Table
                columns={chargeColumns}
                dataSource={[...order.charges].sort(
                  (a, b) => CHARGE_TYPE_ORDER.indexOf(a.charge_type) - CHARGE_TYPE_ORDER.indexOf(b.charge_type)
                )}
                rowKey="id"
                size="small"
                pagination={false}
                summary={() => (
                  <Table.Summary.Row>
                    <Table.Summary.Cell index={0}><Text strong>Итого</Text></Table.Summary.Cell>
                    <Table.Summary.Cell index={1} />
                    <Table.Summary.Cell index={2} align="right">
                      <Text strong>{fmtCny(order.total_sale_cny)}</Text>
                    </Table.Summary.Cell>
                  </Table.Summary.Row>
                )}
              />
            </>
          )}

          <Divider style={{ margin: "12px 0" }} />
          <Row gutter={24}>
            {isLogistics ? (
              Object.entries({ CNY: 1, ...Object.fromEntries(
                Object.entries(chargeRateMap).filter(([k]) => k !== "CNY")
              )}).map(([cur, rate]) => {
                const val = Number(rate) > 0 ? order.total_sale_cny / Number(rate) : null;
                return (
                  <Col key={cur}>
                    <Statistic title={`${t("order.total_sale")} (${cur})`} value={val != null ? fmtCny(val) : "—"} />
                  </Col>
                );
              })
            ) : (
              <>
                <Col><Statistic title={`${t("order.total_sale")} (CNY)`} value={fmtCny(order.total_sale_cny)} /></Col>
                {canSeeCost && (
                  <>
                    <Col><Statistic title={`${t("order.total_cost")} (CNY)`} value={fmtCny(totalCostCny)} /></Col>
                    <Col>
                      <Statistic
                        title={`${t("order.margin")} (CNY)`}
                        value={fmtCny(margin)}
                        valueStyle={{ color: (margin ?? 0) >= 0 ? "#3f8600" : "#cf1322" }}
                      />
                    </Col>
                    <Col>
                      <Statistic
                        title={t("order.margin_pct")}
                        value={marginPct != null ? marginPct.toFixed(1) : "—"}
                        suffix="%"
                      />
                    </Col>
                  </>
                )}
              </>
            )}
          </Row>
        </>
      ),
    },
    {
      key: "files",
      label: t("order.cargo_photo"),
      children: <OrderFilesTab orderId={id!} />,
    },
    {
      key: "payments",
      label: t("tab_payments") || "Платежи",
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 16, padding: "12px 0", borderBottom: "1px solid #f0f0f0" }}>
            <Col>
              <Statistic title={t("payment.total")} value={fmtCny(order.total_sale_cny)} suffix="CNY" valueStyle={{ fontSize: 16 }} />
            </Col>
            <Col>
              <Statistic title={t("order.paid_amount")} value={fmtCny(order.paid_amount_cny)} suffix="CNY"
                valueStyle={{ fontSize: 16, color: "#3f8600" }} />
            </Col>
            <Col>
              <Statistic title={t("order.remaining_amount")} value={fmtCny(order.remaining_amount_cny)} suffix="CNY"
                valueStyle={{ fontSize: 16, color: order.remaining_amount_cny > 0 ? "#cf1322" : "#3f8600" }} />
            </Col>
            <Col flex="auto" style={{ display: "flex", alignItems: "flex-end", justifyContent: "flex-end" }}>
              {order.payment_status !== "paid" && (
                <Button
                  type="primary"
                  onClick={() => navigate(`/payments/new?counterparty_id=${order.client_id}&direction=in&back=/orders/${id}`)}
                >
                  {t("payment.create_for_remaining")} ({fmtCny(order.remaining_amount_cny)} CNY)
                </Button>
              )}
            </Col>
          </Row>
          {(orderPayments || []).length === 0 ? (
            <Text type="secondary">{t("payment.no_payments")}</Text>
          ) : (
            <Table
              dataSource={orderPayments || []}
              rowKey="id"
              size="small"
              pagination={false}
              columns={[
                { title: t("payment.date"), dataIndex: "payment_date", key: "date", width: 110 },
                { title: t("payment.currency"), dataIndex: "currency", key: "cur", width: 80 },
                { title: t("payment.amount"), key: "amount", align: "right",
                  render: (_: any, row: any) => `${Number(row.amount).toLocaleString("ru-RU", {minimumFractionDigits: 2})} ${row.currency}` },
                { title: `${t("payment.alloc_amount")} CNY`, dataIndex: "alloc_cny", key: "alloc_cny", align: "right",
                  render: (v: string) => Number(v).toLocaleString("ru-RU", {minimumFractionDigits: 2}) },
                { title: t("common.actions"), key: "actions", width: 60,
                  render: (_: any, row: any) => (
                    <Button type="link" size="small" onClick={() => navigate(`/payments/${row.id}?back=/orders/${id}`)}>
                      {t("common.open")}
                    </Button>
                  )},
              ]}
            />
          )}
        </div>
      ),
    },
    ...(canSeeCost ? [{
      key: "purchases",
      label: t("nav.purchases"),
      children: (
        <div>
          <Row justify="end" style={{ marginBottom: 12 }}>
            <Button
              type="primary"
              icon={<ShoppingCartOutlined />}
              onClick={() => navigate(`/purchases/new?order_id=${id}`)}
            >
              {t("purchase.create_for_order")}
            </Button>
          </Row>
          {isLogistics ? (
            <Table
              size="small"
              pagination={false}
              rowKey="id"
              dataSource={linkedPurchases}
              columns={[
                { title: t("purchase.number"), dataIndex: "purchase_number", key: "pur_num",
                  render: (num, row: any) => (
                    <Button type="link" size="small" onClick={() => navigate(`/purchases/${row.id}`)}>
                      {num}
                    </Button>
                  )
                },
                { title: t("purchase.supplier"), dataIndex: "supplier_name", key: "supplier" },
                { title: t("purchase.date"), dataIndex: "purchase_date", key: "date" },
                { title: `${t("purchase.total")} (CNY)`, dataIndex: "total_amount_cny", key: "total",
                  align: "right", render: v => fmtCny(v) },
                { title: t("purchase.payment_status"), dataIndex: "payment_status", key: "status",
                  render: (s: string) => (
                    <Tag color={s === "paid" ? "green" : s === "partial" ? "orange" : "red"}>
                      {t(`purchase.status_${s}`)}
                    </Tag>
                  )
                },
              ]}
            />
          ) : (
            <Table
              size="small"
              pagination={false}
              dataSource={order.items.filter(i => (i.purchase_items?.length ?? 0) > 0).flatMap(i =>
                (i.purchase_items || []).map(pi => ({
                  key: pi.id,
                  item_name: i.name,
                  purchase_number: pi.purchase_number,
                  purchase_id: pi.purchase_id,
                  quantity: pi.quantity,
                  cost_price: pi.cost_price,
                  cost_amount: pi.cost_amount,
                }))
              )}
              columns={[
                { title: t("order.item_name"), dataIndex: "item_name", key: "item_name" },
                { title: t("purchase.number"), dataIndex: "purchase_number", key: "pur_num",
                  render: (num, row: any) => (
                    <Button type="link" size="small" onClick={() => navigate(`/purchases/${row.purchase_id}`)}>
                      {num}
                    </Button>
                  )
                },
                { title: t("order.item_quantity"), dataIndex: "quantity", key: "qty", align: "right" },
                { title: t("purchase.cost_price"), dataIndex: "cost_price", key: "cost_price", align: "right" },
                { title: t("purchase.cost_amount_cny"), dataIndex: "cost_amount", key: "cost_amount", align: "right",
                  render: v => fmtCny(v) },
              ]}
            />
          )}
        </div>
      ),
    }] : []),
    {
      key: "expenses",
      label: t("expense.title"),
      children: (
        <div>
          <Row justify="space-between" align="middle" style={{ marginBottom: 12 }}>
            <Col>
              {orderExpenses && orderExpenses.items.length > 0 && (
                <Text type="secondary">
                  {t("expense.total")}: <Text strong>{fmtCny(orderExpenses.total_cny)} CNY</Text>
                </Text>
              )}
            </Col>
            <Col>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => navigate(`/expenses/new?order_id=${id}&back=/orders/${id}`)}
              >
                {t("expense.create_new")}
              </Button>
            </Col>
          </Row>

          {(!orderExpenses || orderExpenses.items.length === 0) ? (
            <Text type="secondary">{t("expense.no_expenses")}</Text>
          ) : (
            <Table<ExpenseListItem>
              dataSource={orderExpenses.items}
              rowKey="id"
              size="small"
              pagination={false}
              columns={[
                {
                  title: t("expense.date"),
                  dataIndex: "expense_date",
                  key: "date",
                  width: 100,
                },
                {
                  title: t("expense.category"),
                  key: "category",
                  render: (_, row) => row.category_name_cn
                    ? `${row.category_name} / ${row.category_name_cn}`
                    : row.category_name,
                },
                {
                  title: t("expense.description"),
                  dataIndex: "description",
                  key: "description",
                },
                {
                  title: t("expense.amount"),
                  key: "amount",
                  align: "right",
                  width: 130,
                  render: (_, row) => `${Number(row.amount).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ${row.currency}`,
                },
                {
                  title: "CNY",
                  dataIndex: "amount_cny",
                  key: "amount_cny",
                  align: "right",
                  width: 110,
                  render: (v: number) => fmtCny(v),
                },
                {
                  title: t("expense.receipt"),
                  key: "receipt",
                  width: 60,
                  align: "center",
                  render: (_, row) => row.receipt_url
                    ? <a href={getFileUrl(row.receipt_url)} target="_blank" rel="noreferrer"><FileOutlined style={{ color: "#1677ff" }} /></a>
                    : null,
                },
                {
                  title: t("common.actions"),
                  key: "actions",
                  width: 70,
                  render: (_, row) => (
                    <Button type="link" size="small" onClick={() => navigate(`/expenses/${row.id}?back=/orders/${id}`)}>
                      {t("common.open")}
                    </Button>
                  ),
                },
              ]}
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} colSpan={4} align="right">
                    <Text strong>{t("expense.total")}:</Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right">
                    <Text strong>{fmtCny(orderExpenses?.total_cny ?? 0)} CNY</Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={5} />
                  <Table.Summary.Cell index={6} />
                </Table.Summary.Row>
              )}
            />
          )}
        </div>
      ),
    },
    ...(canSeeCost ? [{
      key: "profit",
      label: t("order.tab_profit"),
      children: (
        <Row gutter={24} style={{ padding: 16 }}>
          <Col span={6}>
            <Statistic title={`${t("order.total_sale")} (CNY)`} value={fmtCny(order.total_sale_cny)} />
          </Col>
          <Col span={6}>
            <Statistic
              title={`${t("order.total_cost")} (CNY)`}
              value={fmtCny(totalCostCny)}
              valueStyle={{ color: "#cf1322" }}
            />
          </Col>
          {expensesCny > 0 && (
            <Col span={6}>
              <Statistic
                title={`${t("expense.title")} (CNY)`}
                value={fmtCny(expensesCny)}
                valueStyle={{ color: "#cf1322" }}
              />
            </Col>
          )}
          <Col span={6}>
            <Statistic
              title={`${t("order.margin")} (CNY)`}
              value={fmtCny(margin)}
              valueStyle={{ color: (margin ?? 0) >= 0 ? "#3f8600" : "#cf1322" }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title={t("order.margin_pct")}
              value={marginPct != null ? marginPct.toFixed(1) : "—"}
              suffix="%"
              valueStyle={{ color: (marginPct ?? 0) >= 20 ? "#3f8600" : (marginPct ?? 0) >= 0 ? "#faad14" : "#cf1322" }}
            />
          </Col>
        </Row>
      ),
    }] : []),
    {
      key: "history",
      label: t("order.tab_history"),
      children: (
        <Timeline
          items={(history || []).map((h: any) => ({
            children: (
              <div>
                <Text strong>{h.action}</Text>
                {" — "}
                <Text type="secondary">
                  {h.user_name} · {new Date(h.created_at).toLocaleString("ru-RU")}
                </Text>
                {h.changes && (
                  <div style={{ marginTop: 4 }}>
                    <pre style={{ fontSize: 11, margin: 0, background: "#f5f5f5", padding: 4, borderRadius: 4 }}>
                      {JSON.stringify(h.changes, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ),
          }))}
        />
      ),
    },
  ];

  const LOGISTICS_STATUSES = [
    { value: "WAREHOUSE_CN", label: t("order.sync.status_warehouse_cn") },
    { value: "MOVE_CN",      label: t("order.sync.status_move_cn") },
    { value: "BORDER",       label: t("order.sync.status_border") },
    { value: "CUSTOMS",      label: t("order.sync.status_customs") },
    { value: "MOVE_RU",      label: t("order.sync.status_move_ru") },
    { value: "MOSCOW",       label: t("order.sync.status_moscow") },
  ];

  return (
    <div style={{ maxWidth: 1200 }}>
      <Modal
        open={pushStatusOpen}
        title={t("order.sync.push_status")}
        onCancel={() => { setPushStatusOpen(false); pushStatusForm.resetFields(); }}
        onOk={() => pushStatusForm.submit()}
        confirmLoading={pushStatusMutation.isPending}
        okText={t("common.confirm")}
        cancelText={t("common.cancel")}
      >
        <Form
          form={pushStatusForm}
          layout="vertical"
          onFinish={vals => pushStatusMutation.mutate(vals)}
        >
          <Form.Item name="status" label={t("order.sync.status")} rules={[{ required: true }]}>
            <Select options={LOGISTICS_STATUSES} />
          </Form.Item>
          <Form.Item name="comment" label={t("order.sync.comment")}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space align="center">
            <Title level={4} style={{ margin: 0 }}>{order.order_number}</Title>
            <OrderStatusTag status={order.status} />
            <PaymentStatusTag status={order.payment_status} />
          </Space>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate(-1)}>{t("common.back")}</Button>
            {canDownloadPdf && !isLogistics && (
              <Button
                icon={<DownloadOutlined />}
                loading={pdfLoading}
                onClick={handleDownloadPdf}
              >
                {t("order.download_client_pdf")}
              </Button>
            )}
            {canDownloadPdf && isLogistics && (
              <Button
                icon={<DownloadOutlined />}
                loading={logisticsPdfLoading}
                onClick={handleDownloadLogisticsPdf}
              >
                {t("order.download_logistics_pdf")}
              </Button>
            )}
            {canEdit && (
              <Button icon={<EditOutlined />} onClick={() => navigate(`/orders/${id}/edit`)}>
                {t("common.edit")}
              </Button>
            )}
            {canClose && (
              <Popconfirm
                title={t("order.close_confirm")}
                onConfirm={() => closeMutation.mutate()}
                okText={t("common.yes")}
                cancelText={t("common.no")}
              >
                <Button type="primary" icon={<CheckOutlined />} loading={closeMutation.isPending}>
                  {t("order.close_order")}
                </Button>
              </Popconfirm>
            )}
            {canCancel && (
              <>
                <Modal
                  open={cancelModal}
                  title={t("order.cancel_modal_title")}
                  onOk={() => { if (cancelReason.trim()) cancelMutation.mutate(cancelReason.trim()); }}
                  onCancel={() => setCancelModal(false)}
                  okText={t("order.cancel_btn")}
                  cancelText={t("common.cancel")}
                  okButtonProps={{ danger: true, disabled: !cancelReason.trim(), loading: cancelMutation.isPending }}
                  destroyOnClose
                >
                  <p style={{ marginBottom: 8 }}>{t("order.cancel_reason_label")}:</p>
                  <Input.TextArea rows={3} value={cancelReason} onChange={e => setCancelReason(e.target.value)} autoFocus />
                </Modal>
                <Button danger icon={<CloseOutlined />} onClick={() => { setCancelReason(""); setCancelModal(true); }}>
                  {t("order.cancel_order")}
                </Button>
              </>
            )}
          </Space>
        </Col>
      </Row>

      <Tabs items={tabItems} />
    </div>
  );
}
