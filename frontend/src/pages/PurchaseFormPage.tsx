import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams, useParams } from "react-router-dom";
import {
  Form, Input, Select, DatePicker, Button, Card, Typography,
  Space, Row, Col, InputNumber, Table, message, Alert, Spin,
} from "antd";
import { UploadOutlined, PaperClipOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation } from "@tanstack/react-query";
import dayjs from "dayjs";
import { createPurchase, updatePurchase, getPurchase, getAvailableForPurchase, getNextPurchaseNumber } from "../api/purchases";
import { getOrders } from "../api/orders";
import CounterpartySelect from "../components/common/CounterpartySelect";
import apiClient from "../api/client";
import type { AvailableForPurchaseItem } from "../types/order";

const { Title, Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

interface ItemRow extends AvailableForPurchaseItem {
  selected: boolean;
  input_quantity: number;
  cost_price: number;
}

export default function PurchaseFormPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedOrderId = searchParams.get("order_id") ?? undefined;

  const [form] = Form.useForm();
  const [selectedOrderId, setSelectedOrderId] = useState<string | undefined>(preselectedOrderId);
  const [itemRows, setItemRows] = useState<ItemRow[]>([]);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const purchaseDate: dayjs.Dayjs | null = Form.useWatch("purchase_date", form);
  const dateStr = purchaseDate?.format("YYYY-MM-DD");
  const currency: string = Form.useWatch("currency", form) || "CNY";

  const { data: nextNumber } = useQuery({
    queryKey: ["next-purchase-number", dateStr],
    queryFn: () => getNextPurchaseNumber(dateStr!).then(r => r.data),
    enabled: !!dateStr,
  });

  useEffect(() => {
    if (nextNumber) form.setFieldValue("purchase_number", nextNumber.purchase_number);
  }, [nextNumber, form]);

  useEffect(() => {
    form.setFieldsValue({
      purchase_date: dayjs(),
      currency: "CNY",
      rate_to_cny: 1,
    });
  }, [form]);

  const { data: orders } = useQuery({
    queryKey: ["orders-list-brief"],
    queryFn: () => getOrders({ page_size: 100 }).then(r => r.data),
  });

  const { data: availableItems } = useQuery({
    queryKey: ["available-for-purchase", selectedOrderId],
    queryFn: () => getAvailableForPurchase(selectedOrderId!).then(r => r.data),
    enabled: !!selectedOrderId,
  });

  useEffect(() => {
    if (availableItems) {
      setItemRows(availableItems.map(item => ({
        ...item,
        selected: item.available_to_purchase > 0,
        input_quantity: Number(item.available_to_purchase),
        cost_price: 0,
      })));
    }
  }, [availableItems]);

  const selectedOrder = (orders?.items || []).find(o => o.id === selectedOrderId);
  const isLogistics = selectedOrder?.business_type_code === "logistics";

  const createMutation = useMutation({
    mutationFn: createPurchase,
    onSuccess: async (res) => {
      if (pendingFile) {
        try {
          const fd = new FormData();
          fd.append("file", pendingFile);
          await apiClient.post(`/api/purchases/${res.data.id}/files`, fd, {
            headers: { "Content-Type": "multipart/form-data" },
          });
        } catch {
          message.warning("Закупка создана, но файл не загрузился");
        }
      }
      message.success("✓");
      navigate(`/purchases/${res.data.id}`);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleSubmit = (values: any) => {
    if (isLogistics) {
      if (!selectedOrderId) {
        message.error(t("purchase.select_order"));
        return;
      }
      const totalAmount = values.logistics_total_amount;
      if (!totalAmount || totalAmount <= 0) {
        message.error(t("purchase.logistics_amount_required"));
        return;
      }
      createMutation.mutate({
        purchase_number: values.purchase_number,
        supplier_id: values.supplier_id,
        purchase_date: values.purchase_date.format("YYYY-MM-DD"),
        currency: values.currency,
        rate_to_cny: values.rate_to_cny ?? 1,
        notes: values.notes,
        items: [],
        order_id: selectedOrderId,
        total_amount: totalAmount,
      });
    } else {
      const selectedItems = itemRows.filter(r => r.selected && r.input_quantity > 0 && r.cost_price > 0);
      if (selectedItems.length === 0) {
        message.error(t("purchase.no_items_selected"));
        return;
      }
      createMutation.mutate({
        purchase_number: values.purchase_number,
        supplier_id: values.supplier_id,
        purchase_date: values.purchase_date.format("YYYY-MM-DD"),
        currency: values.currency,
        rate_to_cny: values.rate_to_cny ?? 1,
        notes: values.notes,
        items: selectedItems.map(item => ({
          order_item_id: item.id,
          quantity: item.input_quantity,
          cost_price: item.cost_price,
        })),
      });
    }
  };

  const updateRow = (id: string, field: keyof ItemRow, value: any) => {
    setItemRows(rows => rows.map(r => r.id === id ? { ...r, [field]: value } : r));
  };

  const orderOptions = (orders?.items || []).map(o => ({ value: o.id, label: `${o.order_number} — ${o.client_name}` }));

  const totalAmount = itemRows
    .filter(r => r.selected)
    .reduce((sum, r) => sum + r.input_quantity * r.cost_price, 0);

  const logisticsAmount: number = Form.useWatch("logistics_total_amount", form) || 0;
  const rate: number = Form.useWatch("rate_to_cny", form) || 1;
  const logisticsAmountCny = Number((logisticsAmount * rate).toFixed(2));

  return (
    <div style={{ maxWidth: 900 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("purchase.add_new")}</Title>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate("/purchases")}>{t("common.cancel")}</Button>
            <Button type="primary" onClick={() => form.submit()} loading={createMutation.isPending}>
              {t("common.save")}
            </Button>
          </Space>
        </Col>
      </Row>

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="purchase_number" label={t("purchase.number")} rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="purchase_date" label={t("purchase.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="currency" label={t("purchase.currency")} rules={[{ required: true }]}>
                <Select options={CURRENCIES.map(c => ({ value: c, label: c }))} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="rate_to_cny" label={t("purchase.rate_to_cny")}>
                <InputNumber style={{ width: "100%" }} min={0} step={0.01} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="supplier_id" label={t("purchase.supplier")} rules={[{ required: true }]}>
                <CounterpartySelect type="supplier" placeholder={t("purchase.supplier")} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label={t("order.title")}>
                <Select
                  options={orderOptions}
                  value={selectedOrderId}
                  onChange={v => { setSelectedOrderId(v); setItemRows([]); }}
                  showSearch
                  filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())}
                  placeholder={t("purchase.select_order")}
                  allowClear
                />
              </Form.Item>
            </Col>
          </Row>

          {isLogistics && (
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item
                  name="logistics_total_amount"
                  label={`${t("purchase.total_amount")} (${currency})`}
                  rules={[{ required: true, type: "number", min: 0.01 }]}
                >
                  <InputNumber style={{ width: "100%" }} min={0} step={0.01} precision={2} />
                </Form.Item>
              </Col>
              {logisticsAmount > 0 && currency !== "CNY" && (
                <Col span={8}>
                  <Form.Item label={`${t("purchase.total_amount")} (CNY)`}>
                    <InputNumber style={{ width: "100%" }} value={logisticsAmountCny} disabled />
                  </Form.Item>
                </Col>
              )}
            </Row>
          )}

          <Row gutter={16}>
            <Col span={24}>
              <Form.Item name="notes" label={t("purchase.notes")}>
                <Input.TextArea rows={2} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={24}>
              <Form.Item label={t("common.upload_file")}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  style={{ display: "none" }}
                  onChange={e => { setPendingFile(e.target.files?.[0] || null); }}
                />
                <Space>
                  <Button icon={<UploadOutlined />} onClick={() => fileInputRef.current?.click()}>
                    {t("common.choose_file")}
                  </Button>
                  {pendingFile && (
                    <span style={{ color: "#52c41a" }}>
                      <PaperClipOutlined /> {pendingFile.name}
                      <Button type="link" size="small" danger onClick={() => setPendingFile(null)}>✕</Button>
                    </span>
                  )}
                </Space>
              </Form.Item>
            </Col>
          </Row>
        </Card>

        {/* Trade/services: per-item table */}
        {!isLogistics && itemRows.length > 0 && (
          <Card title={t("purchase.items")} style={{ marginBottom: 16 }}>
            <Table
              dataSource={itemRows}
              rowKey="id"
              size="small"
              pagination={false}
              columns={[
                {
                  title: "",
                  key: "sel",
                  width: 40,
                  render: (_, row) => (
                    <input
                      type="checkbox"
                      checked={row.selected}
                      onChange={e => updateRow(row.id, "selected", e.target.checked)}
                    />
                  ),
                },
                {
                  title: t("order.item_name"),
                  key: "name",
                  render: (_, row) => (
                    <div>
                      <div>{row.name}</div>
                      {row.name_cn && <div style={{ color: "#888", fontSize: 11 }}>{row.name_cn}</div>}
                    </div>
                  ),
                },
                {
                  title: t("purchase.available"),
                  key: "avail",
                  align: "right",
                  render: (_, row) => (
                    <Text type={row.available_to_purchase > 0 ? undefined : "danger"}>
                      {Number(row.available_to_purchase)}/{Number(row.quantity)} {row.unit}
                    </Text>
                  ),
                },
                {
                  title: t("order.item_quantity"),
                  key: "qty",
                  width: 110,
                  render: (_, row) => (
                    <InputNumber
                      size="small"
                      min={0}
                      max={Number(row.available_to_purchase)}
                      value={row.input_quantity}
                      disabled={!row.selected}
                      onChange={v => updateRow(row.id, "input_quantity", v ?? 0)}
                      style={{ width: "100%" }}
                    />
                  ),
                },
                {
                  title: `${t("purchase.cost_price")} (${currency})`,
                  key: "cost_price",
                  width: 130,
                  render: (_, row) => (
                    <InputNumber
                      size="small"
                      min={0}
                      value={row.cost_price}
                      disabled={!row.selected}
                      onChange={v => updateRow(row.id, "cost_price", v ?? 0)}
                      style={{ width: "100%" }}
                    />
                  ),
                },
                {
                  title: `${t("purchase.total")} (${currency})`,
                  key: "total",
                  align: "right",
                  render: (_, row) => row.selected
                    ? (row.input_quantity * row.cost_price).toFixed(2)
                    : "—",
                },
              ]}
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} colSpan={5} align="right">
                    <strong>{t("purchase.total")} ({currency}):</strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">
                    <strong>{totalAmount.toFixed(2)}</strong>
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              )}
            />
          </Card>
        )}

        {!isLogistics && selectedOrderId && itemRows.length === 0 && (
          <Alert type="info" message={t("purchase.no_items_available")} showIcon />
        )}
      </Form>
    </div>
  );
}
