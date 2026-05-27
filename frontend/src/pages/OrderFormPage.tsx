import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Form, Input, Select, DatePicker, Button, Card, Typography, Alert,
  Space, Row, Col, Statistic, message, Divider,
} from "antd";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation } from "@tanstack/react-query";
import dayjs from "dayjs";
import { getOrder, createOrder, updateOrder, getNextOrderNumber } from "../api/orders";
import { checkExchangeRates } from "../api/exchangeRates";
import { getCounterparties } from "../api/counterparties";
import { getManagers, getBusinessTypes } from "../api/references";
import OrderItemsEditor from "../components/orders/OrderItemsEditor";
import LogisticsItemsEditor from "../components/orders/LogisticsItemsEditor";
import ChargesEditor from "../components/orders/ChargesEditor";
import OrderFilesTab from "../components/orders/OrderFilesTab";
import ExchangeRateForm from "../components/exchange-rates/ExchangeRateForm";
import type { User } from "../types";

const { Title, Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

interface Props { user: User }

export default function OrderFormPage({ user }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  const isEdit = !!id;

  const [form] = Form.useForm();
  const [rateModalOpen, setRateModalOpen] = useState(false);

  const orderDate: dayjs.Dayjs | null = Form.useWatch("order_date", form);
  const clientId: string = Form.useWatch("client_id", form);
  const items: any[] = Form.useWatch("items", form) || [];
  const charges: any[] = Form.useWatch("charges", form) || [];
  const clientCurrency: string = Form.useWatch("client_currency", form) || "CNY";
  const businessTypeId: string = Form.useWatch("business_type_id", form);

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
  const { data: existingOrder } = useQuery({
    queryKey: ["order", id],
    queryFn: () => getOrder(id!).then(r => r.data),
    enabled: isEdit,
  });

  const isLogistics = useMemo(() => {
    const bt = (businessTypes || []).find((b: any) => b.id === businessTypeId);
    return bt?.code === "logistics";
  }, [businessTypes, businessTypeId]);

  const dateStr = orderDate?.format("YYYY-MM-DD");
  const { data: nextNumber } = useQuery({
    queryKey: ["next-order-number", dateStr],
    queryFn: () => getNextOrderNumber(dateStr!).then(r => r.data),
    enabled: !isEdit && !!dateStr,
  });

  const usedCurrencies = useMemo(() => {
    const set = new Set<string>();
    (items || []).forEach((item: any) => {
      if (!item) return;
      [item.sale_currency, item.price_per_kg_currency, item.cargo_value_currency]
        .forEach(c => { if (c && c !== "CNY") set.add(c); });
    });
    (charges || []).forEach((charge: any) => {
      if (charge?.currency && charge.currency !== "CNY") set.add(charge.currency);
    });
    return Array.from(set);
  }, [items, charges]);

  const { data: rateCheck } = useQuery({
    queryKey: ["exchange-rates-check", dateStr, usedCurrencies],
    queryFn: () => checkExchangeRates(dateStr!, usedCurrencies).then(r => r.data),
    enabled: !!dateStr && usedCurrencies.length > 0,
  });

  const rates: Record<string, number> = useMemo(() => {
    if (!rateCheck) return { CNY: 1 };
    return { CNY: 1, ...rateCheck.rates };
  }, [rateCheck]);

  const { totalSale } = useMemo(() => {
    if (isLogistics) {
      let sale = 0;
      (charges || []).forEach((charge: any) => {
        if (!charge?.amount) return;
        const r = rates[charge?.currency ?? "CNY"] ?? null;
        if (r !== null) sale += Number(charge.amount) * r;
      });
      (items || []).forEach((item: any) => {
        if (!item?.weight_kg || !item?.price_per_kg) return;
        const r = rates[item?.price_per_kg_currency ?? "CNY"] ?? null;
        if (r !== null) sale += Number(item.weight_kg) * Number(item.price_per_kg) * r;
      });
      return { totalSale: sale };
    }
    let sale = 0;
    (items || []).forEach((item: any) => {
      if (!item) return;
      const sr = rates[item?.sale_currency ?? "CNY"] ?? null;
      const qty = Number(item?.quantity) || 0;
      if (sr !== null) sale += qty * (Number(item?.sale_price) || 0) * sr;
    });
    return { totalSale: sale };
  }, [items, charges, rates, isLogistics]);

  // Multi-currency totals for logistics
  const multiTotals = useMemo(() => {
    if (!isLogistics) return null;
    return {
      CNY: totalSale,
      USD: rates.USD ? totalSale / rates.USD : null,
      RUB: rates.RUB ? totalSale / rates.RUB : null,
      USDT: rates.USDT ? totalSale / rates.USDT : null,
    };
  }, [isLogistics, totalSale, rates]);

  useEffect(() => {
    if (!isEdit) {
      form.setFieldsValue({ order_date: dayjs(), manager_id: user.id, client_currency: "CNY" });
    }
  }, [isEdit, user.id, form]);

  useEffect(() => {
    if (!isEdit && nextNumber) {
      form.setFieldValue("order_number", nextNumber.order_number);
    }
  }, [nextNumber, isEdit, form]);

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
        recipient: existingOrder.recipient,
        destination: existingOrder.destination,
        arrival_date: existingOrder.arrival_date ? dayjs(existingOrder.arrival_date) : null,
        tracking_number: existingOrder.tracking_number,
        items: existingOrder.items.map(i => ({
          name: i.name, name_cn: i.name_cn,
          quantity: i.quantity != null ? Number(i.quantity) : undefined,
          unit: i.unit,
          preferred_supplier_id: i.preferred_supplier_id,
          sale_price: i.sale_price != null ? Number(i.sale_price) : undefined,
          sale_currency: i.sale_currency,
          weight_kg: i.weight_kg != null ? Number(i.weight_kg) : undefined,
          volume_m3: i.volume_m3 != null ? Number(i.volume_m3) : undefined,
          price_per_kg: i.price_per_kg != null ? Number(i.price_per_kg) : undefined,
          price_per_kg_currency: i.price_per_kg_currency,
          cargo_value: i.cargo_value != null ? Number(i.cargo_value) : undefined,
          cargo_value_currency: i.cargo_value_currency,
          places_count: i.places_count,
        })),
        charges: (() => {
          const CHARGE_TYPES = ["delivery","insurance_percent","insurance_cost","china_delivery","extra_packing","loaders"];
          const byType: Record<string, any> = {};
          (existingOrder.charges || []).forEach(c => { byType[c.charge_type] = c; });
          return CHARGE_TYPES.map(type => ({
            charge_type: type,
            amount: byType[type] ? Number(byType[type].amount) : undefined,
            currency: byType[type]?.currency || "USD",
          }));
        })(),
      });
    }
  }, [existingOrder, isEdit, form]);

  useEffect(() => {
    if (clientId && clients) {
      const client = clients.items.find((c: any) => c.id === clientId);
      if (client) {
        form.setFieldValue("client_currency", client.default_currency);
        if (isLogistics && !form.getFieldValue("recipient")) {
          form.setFieldValue("recipient", client.name);
        }
      }
    }
  }, [clientId, clients, form, isLogistics]);

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
    const missingRates = rateCheck?.missing ?? [];
    if (missingRates.length > 0) {
      message.error(t("order.missing_rate_warning", { currencies: missingRates.join(", "), date: dateStr }));
      return;
    }

    // Filter out empty charges
    const charges = (values.charges || []).filter((c: any) => c?.amount != null && c?.amount > 0);

    const payload = {
      ...values,
      order_date: values.order_date?.format("YYYY-MM-DD"),
      arrival_date: values.arrival_date?.format("YYYY-MM-DD") || null,
      charges,
      items: (values.items || []).map((item: any) => ({
        ...item,
        quantity: item.quantity != null ? Number(item.quantity) : undefined,
        sale_price: item.sale_price != null ? Number(item.sale_price) : undefined,
        weight_kg: item.weight_kg != null ? Number(item.weight_kg) : undefined,
        volume_m3: item.volume_m3 != null ? Number(item.volume_m3) : undefined,
        price_per_kg: item.price_per_kg != null ? Number(item.price_per_kg) : undefined,
        cargo_value: item.cargo_value != null ? Number(item.cargo_value) : undefined,
      })),
    };
    if (isEdit) updateMutation.mutate(payload);
    else createMutation.mutate(payload);
  };

  const clientOptions = (clients?.items || []).map((c: any) => ({ value: c.id, label: c.name }));
  const managerOptions = (managers || []).map((m: any) => ({ value: m.id, label: m.full_name }));
  const btOptions = (businessTypes || []).map((bt: any) => ({ value: bt.id, label: bt.name }));
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
          action={<Button size="small" onClick={() => setRateModalOpen(true)}>{t("order.add_rate")}</Button>}
          showIcon
        />
      )}

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        {/* Main fields */}
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

        {/* Logistics: route info */}
        {isLogistics && (
          <Card title={t("order.routing_info")} style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={6}>
                <Form.Item name="recipient" label={t("order.recipient")}>
                  <Input />
                </Form.Item>
              </Col>
              <Col span={6}>
                <Form.Item name="destination" label={t("order.destination")}>
                  <Input />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="arrival_date" label={t("order.arrival_date")}>
                  <DatePicker style={{ width: "100%" }} />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name="tracking_number" label={t("order.tracking_number")}>
                  <Input />
                </Form.Item>
              </Col>
            </Row>
          </Card>
        )}

        {/* Items */}
        <Card
          title={isLogistics ? t("order.cargo_details") : t("order.items")}
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
          {isLogistics ? (
            <LogisticsItemsEditor form={form} rates={rates} />
          ) : (
            <OrderItemsEditor form={form} rates={rates} clientCurrency={clientCurrency} />
          )}

          {/* Totals */}
          {isLogistics && multiTotals ? (
            <>
              <Divider style={{ margin: "12px 0" }} />
              <Row gutter={24}>
                {(["CNY", "USD", "RUB", "USDT"] as const).map(cur => (
                  <Col key={cur}>
                    <Statistic
                      title={`${t("order.total_sale")} (${cur})`}
                      value={multiTotals[cur] != null ? multiTotals[cur]!.toFixed(2) : "—"}
                      valueStyle={rates[cur] == null && cur !== "CNY" ? { color: "#cf1322" } : undefined}
                    />
                  </Col>
                ))}
              </Row>
            </>
          ) : !isLogistics ? (
            <Row gutter={24} style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid #f0f0f0" }}>
              <Col><Statistic title={`${t("order.total_sale")} (CNY)`} value={totalSale.toFixed(2)} /></Col>
            </Row>
          ) : null}
        </Card>

        {/* Logistics: cost breakdown */}
        {isLogistics && (
          <Card title={t("order.cost_breakdown")} style={{ marginBottom: 16 }}>
            <ChargesEditor form={form} rates={rates} />
          </Card>
        )}

        {/* Files section (edit mode only) */}
        {isEdit && (
          <Card title={t("order.cargo_photo")} style={{ marginBottom: 16 }}>
            <OrderFilesTab orderId={id!} />
          </Card>
        )}
        {!isEdit && (
          <Card title={t("order.cargo_photo")} style={{ marginBottom: 16 }}>
            <Text type="secondary">{t("order.files_after_save")}</Text>
          </Card>
        )}
      </Form>

      <ExchangeRateForm
        open={rateModalOpen}
        defaultDate={dateStr}
        onClose={() => setRateModalOpen(false)}
      />
    </div>
  );
}
