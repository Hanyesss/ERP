import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Form, Input, Select, DatePicker, Button, Card, Typography, Alert,
  Space, Row, Col, Statistic, message,
} from "antd";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation } from "@tanstack/react-query";
import dayjs from "dayjs";
import { getOrder, createOrder, updateOrder, getNextOrderNumber } from "../api/orders";
import { checkExchangeRates } from "../api/exchangeRates";
import { getCounterparties } from "../api/counterparties";
import { getManagers, getBusinessTypes } from "../api/references";
import OrderItemsEditor from "../components/orders/OrderItemsEditor";
import ExchangeRateForm from "../components/exchange-rates/ExchangeRateForm";
import type { User } from "../types";

const { Title, Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT"];

interface Props { user: User }

export default function OrderFormPage({ user }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  const isEdit = !!id;

  const [form] = Form.useForm();
  const [rateModalOpen, setRateModalOpen] = useState(false);

  // Watch reactive values
  const orderDate: dayjs.Dayjs | null = Form.useWatch("order_date", form);
  const clientId: string = Form.useWatch("client_id", form);
  const items: any[] = Form.useWatch("items", form) || [];
  const clientCurrency: string = Form.useWatch("client_currency", form) || "CNY";

  // Reference data
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

  // Existing order for edit
  const { data: existingOrder } = useQuery({
    queryKey: ["order", id],
    queryFn: () => getOrder(id!).then(r => r.data),
    enabled: isEdit,
  });

  // Auto-generate order number for new
  const dateStr = orderDate?.format("YYYY-MM-DD");
  const { data: nextNumber } = useQuery({
    queryKey: ["next-order-number", dateStr],
    queryFn: () => getNextOrderNumber(dateStr!).then(r => r.data),
    enabled: !isEdit && !!dateStr,
  });

  // Determine which non-CNY currencies are used in items
  const usedCurrencies = useMemo(() => {
    const set = new Set<string>();
    (items || []).forEach((item: any) => {
      if (item?.sale_currency && item.sale_currency !== "CNY") set.add(item.sale_currency);
      if (item?.cost_currency && item.cost_currency !== "CNY") set.add(item.cost_currency);
    });
    return Array.from(set);
  }, [items]);

  // Check exchange rates
  const { data: rateCheck } = useQuery({
    queryKey: ["exchange-rates-check", dateStr, usedCurrencies],
    queryFn: () => checkExchangeRates(dateStr!, usedCurrencies).then(r => r.data),
    enabled: !!dateStr && usedCurrencies.length > 0,
  });

  const rates: Record<string, number> = useMemo(() => {
    if (!rateCheck) return { CNY: 1 };
    return { CNY: 1, ...rateCheck.rates };
  }, [rateCheck]);

  // Real-time totals
  const { totalSale, totalCost } = useMemo(() => {
    let sale = 0, cost = 0;
    (items || []).forEach((item: any) => {
      if (!item) return;
      const sr = rates[item?.sale_currency ?? "CNY"] ?? null;
      const cr = rates[item?.cost_currency ?? "CNY"] ?? null;
      const qty = Number(item?.quantity) || 0;
      if (sr !== null) sale += qty * (Number(item?.sale_price) || 0) * sr;
      if (cr !== null) cost += qty * (Number(item?.cost_price) || 0) * cr;
    });
    return { totalSale: sale, totalCost: cost };
  }, [items, rates]);

  // Set defaults for new order
  useEffect(() => {
    if (!isEdit) {
      form.setFieldsValue({ order_date: dayjs(), manager_id: user.id, client_currency: "CNY" });
    }
  }, [isEdit, user.id, form]);

  // Set next number
  useEffect(() => {
    if (!isEdit && nextNumber) {
      form.setFieldValue("order_number", nextNumber.order_number);
    }
  }, [nextNumber, isEdit, form]);

  // Populate edit form
  useEffect(() => {
    if (isEdit && existingOrder) {
      form.setFieldsValue({
        order_number: existingOrder.order_number,
        order_date: dayjs(existingOrder.order_date),
        client_id: existingOrder.client_id,
        business_type_id: existingOrder.business_type_id,
        manager_id: existingOrder.manager_id,
        client_currency: existingOrder.client_currency,
        notes: existingOrder.notes,
        items: existingOrder.items.map(i => ({
          name: i.name, name_cn: i.name_cn,
          quantity: Number(i.quantity), unit: i.unit,
          cost_price: Number(i.cost_price), cost_currency: i.cost_currency,
          supplier_id: i.supplier_id,
          sale_price: Number(i.sale_price), sale_currency: i.sale_currency,
        })),
      });
    }
  }, [existingOrder, isEdit, form]);

  // Auto-set client currency when client changes
  useEffect(() => {
    if (clientId && clients) {
      const client = clients.items.find(c => c.id === clientId);
      if (client) form.setFieldValue("client_currency", client.default_currency);
    }
  }, [clientId, clients, form]);

  const createMutation = useMutation({
    mutationFn: createOrder,
    onSuccess: (res) => { message.success("✓"); navigate(`/orders/${res.data.id}`); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const updateMutation = useMutation({
    mutationFn: (data: any) => updateOrder(id!, data),
    onSuccess: (res) => { message.success("✓"); navigate(`/orders/${res.data.id}`); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleSubmit = (values: any) => {
    if (rateCheck && rateCheck.missing.length > 0) {
      message.error(t("order.missing_rate_warning", { currencies: rateCheck.missing.join(", "), date: dateStr }));
      return;
    }
    const payload = {
      ...values,
      order_date: values.order_date?.format("YYYY-MM-DD"),
      items: (values.items || []).map((item: any) => ({
        ...item,
        quantity: Number(item.quantity),
        cost_price: Number(item.cost_price),
        sale_price: Number(item.sale_price),
      })),
    };
    if (isEdit) updateMutation.mutate(payload);
    else createMutation.mutate(payload);
  };

  const clientOptions = (clients?.items || []).map(c => ({ value: c.id, label: c.name }));
  const managerOptions = (managers || []).map(m => ({ value: m.id, label: m.full_name }));
  const btOptions = (businessTypes || []).map(bt => ({ value: bt.id, label: bt.name }));
  const missingRates = rateCheck?.missing ?? [];

  return (
    <div style={{ maxWidth: 1200 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            {isEdit ? t("order.edit") : t("order.create_new")}
          </Title>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate("/orders")}>{t("common.cancel")}</Button>
            <Button type="primary" onClick={() => form.submit()}
              loading={createMutation.isPending || updateMutation.isPending}>
              {t("common.save")}
            </Button>
          </Space>
        </Col>
      </Row>

      {missingRates.length > 0 && (
        <Alert
          type="warning"
          style={{ marginBottom: 16 }}
          message={t("order.missing_rate_warning", { currencies: missingRates.join(", "), date: dateStr })}
          action={
            <Button size="small" onClick={() => setRateModalOpen(true)}>{t("order.add_rate")}</Button>
          }
          showIcon
        />
      )}

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Card title={t("order.tab_main")} style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="order_number" label={t("order.number")} rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="order_date" label={t("order.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="client_id" label={t("order.client")} rules={[{ required: true }]}>
                <Select showSearch options={clientOptions} placeholder={t("order.client")}
                  filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="client_currency" label={t("order.currency")} rules={[{ required: true }]}>
                <Select options={CURRENCIES.map(c => ({ value: c, label: c }))} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="business_type_id" label={t("order.business_type")} rules={[{ required: true }]}>
                <Select options={btOptions} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="manager_id" label={t("order.manager")} rules={[{ required: true }]}>
                <Select options={managerOptions} />
              </Form.Item>
            </Col>
            <Col span={18}>
              <Form.Item name="notes" label={t("order.notes")}>
                <Input.TextArea rows={2} />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Card
          title={t("order.items")}
          style={{ marginBottom: 16 }}
          extra={
            <Space size="large">
              {usedCurrencies.map(cur => (
                <Text key={cur} type={rates[cur] ? undefined : "danger"}>
                  {cur}/CNY: {rates[cur] ? rates[cur].toFixed(4) : "⚠ нет курса"}
                </Text>
              ))}
            </Space>
          }
        >
          <OrderItemsEditor form={form} rates={rates} clientCurrency={clientCurrency} />

          <Row gutter={24} style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid #f0f0f0" }}>
            <Col>
              <Statistic title={`${t("order.total_sale")} (CNY)`} value={totalSale.toFixed(2)} />
            </Col>
            <Col>
              <Statistic title={`${t("order.total_cost")} (CNY)`} value={totalCost.toFixed(2)} />
            </Col>
            <Col>
              <Statistic
                title={`${t("order.margin")} (CNY)`}
                value={(totalSale - totalCost).toFixed(2)}
                valueStyle={{ color: totalSale - totalCost >= 0 ? "#3f8600" : "#cf1322" }}
              />
            </Col>
            <Col>
              <Statistic
                title={t("order.margin_pct")}
                value={totalSale > 0 ? (((totalSale - totalCost) / totalSale) * 100).toFixed(1) : "0"}
                suffix="%"
              />
            </Col>
          </Row>
        </Card>
      </Form>

      <ExchangeRateForm
        open={rateModalOpen}
        defaultDate={dateStr}
        onClose={() => setRateModalOpen(false)}
      />
    </div>
  );
}
