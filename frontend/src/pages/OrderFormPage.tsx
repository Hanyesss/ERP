import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useNavigationGuard } from "../contexts/NavigationGuardContext";
import {
  Form, Input, Select, DatePicker, Button, Card, Typography, Alert,
  Space, Row, Col, Statistic, message, Divider, Tooltip, Tag, Checkbox, Modal,
} from "antd";
import { UploadOutlined, DeleteOutlined, EditOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { getOrder, createOrder, updateOrder, getNextOrderNumber } from "../api/orders";
import { checkExchangeRates } from "../api/exchangeRates";
import { getCounterparties } from "../api/counterparties";
import { getManagers, getBusinessTypes } from "../api/references";
import { getWarehouses } from "../api/warehouses";
import OrderItemsEditor, { type PendingItemPhotos } from "../components/orders/OrderItemsEditor";
import LogisticsItemsEditor from "../components/orders/LogisticsItemsEditor";
import ChargesEditor from "../components/orders/ChargesEditor";
import OrderFilesTab from "../components/orders/OrderFilesTab";
import ItemPhotosEditor from "../components/orders/ItemPhotosEditor";
import ExchangeRateForm from "../components/exchange-rates/ExchangeRateForm";
import CounterpartySelect from "../components/common/CounterpartySelect";
import { uploadItemPhoto, uploadOrderFile } from "../api/orders";
import type { User } from "../types";
import { compressImage } from "../utils/compressImage";

const { Title, Text } = Typography;

interface PendingOrderFile { uid: string; file: File; fileType: string; }

const ORDER_FILE_TYPES = [
  { value: "cargo_photo", labelKey: "order.file_type_cargo_photo" },
  { value: "invoice",     labelKey: "order.file_type_invoice" },
  { value: "packing",     labelKey: "order.file_type_packing" },
  { value: "other",       labelKey: "order.file_type_other" },
];
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

interface Props { user: User }

export default function OrderFormPage({ user }: Props) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  const isEdit = !!id;

  const qc = useQueryClient();
  const formInitializedRef = useRef(false);
  const [form] = Form.useForm();
  const [rateModalOpen, setRateModalOpen] = useState(false);
  const [clientPhone, setClientPhone] = useState<string | null>(null);
  const [pendingPhotos, setPendingPhotos] = useState<PendingItemPhotos>({});
  const [savedItemIdByKey, setSavedItemIdByKey] = useState<Record<number, string>>({});
  const [purchasedItemIds, setPurchasedItemIds] = useState<Set<string>>(new Set());
  const [pendingOrderFiles, setPendingOrderFiles] = useState<PendingOrderFile[]>([]);
  const [pendingFileType, setPendingFileType] = useState("cargo_photo");
  const pendingFilesInputRef = useRef<HTMLInputElement>(null);
  const orderNumberEditedRef = useRef(false); // защита от перезаписи ручного ввода

  const DRAFT_KEY = "draft_order_new_v2";
  const [isDirty, setIsDirty] = useState(false);
  const [draftModalOpen, setDraftModalOpen] = useState(false);
  const [draftAvailable, setDraftAvailable] = useState(false);
  const guardResolveRef = useRef<((allow: boolean) => void) | null>(null);
  const { registerGuard, unregisterGuard } = useNavigationGuard();

  const markDirty = () => setIsDirty(true);
  const clearDirty = () => setIsDirty(false);

  const guardFn = useCallback((): Promise<boolean> => new Promise(resolve => {
    guardResolveRef.current = resolve;
    setDraftModalOpen(true);
  }), []);

  useEffect(() => {
    if (isDirty) registerGuard(guardFn); else unregisterGuard();
    return () => unregisterGuard();
  }, [isDirty, guardFn, registerGuard, unregisterGuard]);

  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  useEffect(() => {
    if (!isEdit && localStorage.getItem(DRAFT_KEY)) setDraftAvailable(true);
  }, [isEdit]);

  const resolveGuard = (allow: boolean) => {
    guardResolveRef.current?.(allow);
    guardResolveRef.current = null;
  };

  const handleSaveDraft = () => {
    const v = form.getFieldsValue();
    const items = (v.items || []).map((item: any) => item ? {
      name: item.name, name_cn: item.name_cn, model: item.model,
      specification: item.specification, quantity: item.quantity, unit: item.unit,
      sale_price: item.sale_price, sale_currency: item.sale_currency,
      preferred_supplier_id: item.preferred_supplier_id,
      weight_kg: item.weight_kg, volume_m3: item.volume_m3,
      price_per_kg: item.price_per_kg, price_per_kg_currency: item.price_per_kg_currency,
      cargo_value: item.cargo_value, cargo_value_currency: item.cargo_value_currency,
      supplier_id: item.supplier_id, places_count: item.places_count,
    } : null);
    const charges = (v.charges || []).map((c: any) => c ? { amount: c.amount, currency: c.currency } : null);
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      order_number: v.order_number,
      order_date: v.order_date?.format?.("YYYY-MM-DD"),
      arrival_date: v.arrival_date?.format?.("YYYY-MM-DD"),
      client_id: v.client_id, business_type_id: v.business_type_id,
      client_currency: v.client_currency, warehouse_id: v.warehouse_id,
      notes: v.notes, excluded_from_accounting: v.excluded_from_accounting,
      items, charges,
    }));
    clearDirty();
    setDraftModalOpen(false);
    resolveGuard(true);
  };

  const handleDiscardDraft = () => {
    if (!isEdit) localStorage.removeItem(DRAFT_KEY);
    clearDirty();
    setDraftModalOpen(false);
    resolveGuard(true);
  };

  const handleCancelNav = () => {
    setDraftModalOpen(false);
    resolveGuard(false);
  };

  const handleRestoreDraft = () => {
    const saved = localStorage.getItem(DRAFT_KEY);
    if (!saved) return;
    try {
      const d = JSON.parse(saved);
      form.setFieldsValue({
        order_number: d.order_number,
        order_date: d.order_date ? dayjs(d.order_date) : undefined,
        arrival_date: d.arrival_date ? dayjs(d.arrival_date) : undefined,
        client_id: d.client_id, business_type_id: d.business_type_id,
        client_currency: d.client_currency, warehouse_id: d.warehouse_id,
        notes: d.notes, excluded_from_accounting: d.excluded_from_accounting,
        items: d.items ?? [], charges: d.charges ?? [],
      });
      setDraftAvailable(false);
      markDirty();
    } catch { localStorage.removeItem(DRAFT_KEY); setDraftAvailable(false); }
  };

  const safeNavigate = (to: string | number) => {
    if (!isDirty) { navigate(to as any); return; }
    guardFn().then(allow => { if (allow) navigate(to as any); });
  };

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

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => getWarehouses().then(r => r.data),
  });

  const businessTypeCode = useMemo(() => {
    const bt = (businessTypes || []).find((b: any) => b.id === businessTypeId);
    return bt?.code as string | undefined;
  }, [businessTypes, businessTypeId]);

  const isLogistics = businessTypeCode === "logistics";

  const clientCode = useMemo(() => {
    if (!clientId || !clients) return undefined;
    return clients.items.find((c: any) => c.id === clientId)?.code as string | undefined;
  }, [clientId, clients]);

  const totalPlaces = useMemo(() => {
    return (items || []).reduce((sum: number, item: any) => sum + (Number(item?.places_count) || 0), 0);
  }, [items]);

  const dateStr = orderDate?.format("YYYY-MM-DD");
  const { data: nextNumber } = useQuery({
    queryKey: ["next-order-number", dateStr, businessTypeCode, clientCode, totalPlaces],
    queryFn: () => getNextOrderNumber(dateStr!, {
      business_type_code: businessTypeCode,
      client_code: clientCode,
      places_count: isLogistics ? totalPlaces : undefined,
    }).then(r => r.data),
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
        // insurance_percent — просто процент, не денежная сумма, не добавляем к итогу
        if (charge?.charge_type === "insurance_percent") return;
        if (!charge?.amount) return;
        const r = rates[charge?.currency ?? "CNY"] ?? null;
        if (r !== null) sale += Number(charge.amount) * r;
      });
      // delivery (charges[0]) уже содержит weight × price_per_kg — не добавляем повторно
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
      form.setFieldsValue({ order_date: dayjs(), client_currency: "CNY" });
    }
  }, [isEdit, form]);

  useEffect(() => {
    if (!isEdit && nextNumber && !orderNumberEditedRef.current) {
      form.setFieldValue("order_number", nextNumber.order_number);
    }
  }, [nextNumber, isEdit, form]);

  useEffect(() => {
    if (!isEdit || !existingOrder || formInitializedRef.current) return;
    formInitializedRef.current = true;
    {
      setClientPhone((existingOrder as any).client_phone || null);
      setPendingPhotos({});
      // Map Form.List key (=index for initial load) → saved item ID
      const idMap: Record<number, string> = {};
      const purchasedIds = new Set<string>();
      (existingOrder.items || []).forEach((item: any, idx: number) => {
        if (item.id) {
          idMap[idx] = item.id;
          const hasPurchase = (item.purchase_items && item.purchase_items.length > 0)
            || (item.purchased_quantity != null && Number(item.purchased_quantity) > 0);
          if (hasPurchase) {
            purchasedIds.add(item.id);
          }
        }
      });
      setSavedItemIdByKey(idMap);
      setPurchasedItemIds(purchasedIds);

      form.setFieldsValue({
        order_number: existingOrder.order_number,
        order_date: dayjs(existingOrder.order_date),
        client_id: existingOrder.client_id,
        business_type_id: existingOrder.business_type_id,
        client_currency: existingOrder.client_currency,
        notes: existingOrder.notes,
        excluded_from_accounting: existingOrder.excluded_from_accounting ?? false,
        recipient: existingOrder.recipient,
        destination: existingOrder.destination,
        arrival_date: existingOrder.arrival_date ? dayjs(existingOrder.arrival_date) : null,
        tracking_number: existingOrder.tracking_number,
        warehouse_id: existingOrder.warehouse_id || undefined,
        items: existingOrder.items.map((i: any) => ({
          id: i.id,          // ← передаём id для корректного upsert на бэке
          name: i.name, name_cn: i.name_cn,
          model: i.model,
          specification: i.specification,
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
        setClientPhone(client.phone || client.contact_info?.phone || null);
        if (isLogistics && !form.getFieldValue("recipient")) {
          form.setFieldValue("recipient", client.name);
        }
      }
    }
  }, [clientId, clients, form, isLogistics]);

  // Auto-fill delivery amount = sum(weight_kg × price_per_kg) per item
  useEffect(() => {
    if (!isLogistics) return;
    const byCurrency: Record<string, number> = {};
    (items || []).forEach((item: any) => {
      if (!item?.weight_kg || !item?.price_per_kg) return;
      const cur = item.price_per_kg_currency || "USD";
      byCurrency[cur] = (byCurrency[cur] || 0) + Number(item.weight_kg) * Number(item.price_per_kg);
    });
    const currencies = Object.keys(byCurrency);
    if (currencies.length === 0) return;
    if (currencies.length === 1) {
      form.setFieldValue(["charges", 0, "amount"], parseFloat(byCurrency[currencies[0]].toFixed(2)));
      form.setFieldValue(["charges", 0, "currency"], currencies[0]);
    } else {
      let total = 0;
      currencies.forEach(cur => { total += byCurrency[cur] * (rates[cur] || 1); });
      form.setFieldValue(["charges", 0, "amount"], parseFloat(total.toFixed(2)));
      form.setFieldValue(["charges", 0, "currency"], "CNY");
    }
  }, [items, isLogistics, rates, form]);

  // Auto-fill insurance_cost = total cargo value × insurance_percent / 100 (in cargo currency)
  useEffect(() => {
    if (!isLogistics) return;
    const pct = Number(charges?.[1]?.amount) || 0;
    if (pct <= 0) return;
    // Group cargo values by currency (no CNY conversion — keep original currency)
    const byCurrency: Record<string, number> = {};
    (items || []).forEach((item: any) => {
      if (!item?.cargo_value) return;
      const cur = item.cargo_value_currency || "USD";
      byCurrency[cur] = (byCurrency[cur] || 0) + Number(item.cargo_value);
    });
    const currencies = Object.keys(byCurrency);
    if (currencies.length === 0) return;
    if (currencies.length === 1) {
      // Single currency: keep it as-is
      const cur = currencies[0];
      form.setFieldValue(["charges", 2, "amount"], parseFloat((byCurrency[cur] * pct / 100).toFixed(2)));
      form.setFieldValue(["charges", 2, "currency"], cur);
    } else {
      // Mixed currencies: convert all to CNY
      let totalCny = 0;
      currencies.forEach(cur => { totalCny += byCurrency[cur] * (rates[cur] || 1); });
      form.setFieldValue(["charges", 2, "amount"], parseFloat((totalCny * pct / 100).toFixed(2)));
      form.setFieldValue(["charges", 2, "currency"], "CNY");
    }
  }, [items, charges, isLogistics, rates, form]);

  const uploadPendingOrderFiles = async (orderId: string) => {
    if (!pendingOrderFiles.length) return;
    await Promise.all(
      pendingOrderFiles.map(pf => uploadOrderFile(orderId, pf.file, pf.fileType).catch(() => null))
    );
    setPendingOrderFiles([]);
  };

  const uploadPendingPhotos = async (savedItems: any[]) => {
    const entries = Object.entries(pendingPhotos);
    if (!entries.length) return;
    const uploads: Promise<any>[] = [];
    for (const [indexStr, photos] of entries) {
      const idx = Number(indexStr);
      const item = savedItems[idx];
      if (!item?.id) continue;
      for (const ph of photos) {
        uploads.push(uploadItemPhoto(item.id, ph.file).catch(() => null));
      }
    }
    await Promise.all(uploads);
    setPendingPhotos({});
  };

  const createMutation = useMutation({
    mutationFn: createOrder,
    onSuccess: async (res) => {
      await uploadPendingPhotos(res.data.items || []);
      await uploadPendingOrderFiles(res.data.id);
      message.success("✓");
      clearDirty();
      localStorage.removeItem(DRAFT_KEY);
      navigate(`/orders/${res.data.id}`);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const updateMutation = useMutation({
    mutationFn: (data: any) => updateOrder(id!, data),
    onSuccess: async (res) => {
      await uploadPendingPhotos(res.data.items || []);
      qc.invalidateQueries({ queryKey: ["order", id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      message.success("✓");
      clearDirty();
      navigate(`/orders/${res.data.id}`);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleSubmit = (values: any) => {
    const missingRates = rateCheck?.missing ?? [];
    if (!isLogistics && missingRates.length > 0) {
      message.error(t("order.missing_rate_warning", { currencies: missingRates.join(", "), date: dateStr }));
      return;
    }

    // Filter out empty charges
    const charges = (values.charges || []).filter((c: any) => c?.amount != null && c?.amount > 0);

    // manager_id is excluded — always set server-side to current user
    const { manager_id: _ignored, ...restValues } = values;
    // Read items directly from form store (includes `id` set via setFieldsValue,
    // which onFinish/getFieldsValue might miss for unregistered sub-fields)
    const rawItems: any[] = form.getFieldValue("items") || [];
    const payload = {
      ...restValues,
      order_date: values.order_date?.format("YYYY-MM-DD"),
      arrival_date: values.arrival_date?.format("YYYY-MM-DD") || null,
      charges,
      items: rawItems.map((item: any) => ({
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

  const btOptions = (businessTypes || []).map((bt: any) => ({ value: bt.id, label: i18n.language === "zh" && bt.name_cn ? bt.name_cn : bt.name }));
  // Manager name: for edit — from loaded order; for new — current user
  const managerName = isEdit
    ? ((existingOrder as any)?.manager_name || user.full_name)
    : user.full_name;
  const missingRates = rateCheck?.missing ?? [];

  // Производные значения курсов для виджета и предзаполнения формы
  const ratesForWidget = useMemo(() => {
    const r = rateCheck?.rates ?? {};
    const rub = r["RUB"] as number | undefined;
    const usd = r["USD"] as number | undefined;
    const usdt = r["USDT"] as number | undefined;
    return {
      cny_to_rub:  rub              ? parseFloat((1 / rub).toFixed(4))         : undefined,
      usd_to_rub:  rub && usd       ? parseFloat((usd / rub).toFixed(4))        : undefined,
      usd_to_cny:  usd              ? parseFloat(Number(usd).toFixed(4))        : undefined,
      usd_to_usdt: usd && usdt      ? parseFloat((usd / usdt).toFixed(4))       : undefined,
    };
  }, [rateCheck]);

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
            <Button onClick={() => safeNavigate(-1)}>{t("common.cancel")}</Button>
            <Button type="primary" onClick={() => form.submit()}
              loading={createMutation.isPending || updateMutation.isPending}>
              {t("common.save")}
            </Button>
          </Space>
        </Col>
      </Row>

      {dateStr && (
        <Card
          size="small"
          style={{ marginBottom: 16, background: "#fafafa" }}
          extra={
            <Button size="small" icon={<EditOutlined />} onClick={() => setRateModalOpen(true)}>
              {t("exchange_rate.edit_rates")}
            </Button>
          }
          title={<span style={{ fontSize: 13 }}>{t("exchange_rate.rates_for_date")}: <b>{dateStr}</b></span>}
        >
          <Row gutter={[24, 0]}>
            {[
              { label: "1 CNY = ? RUB", value: ratesForWidget.cny_to_rub },
              { label: "1 USD = ? RUB", value: ratesForWidget.usd_to_rub },
              { label: "1 USD = ? CNY", value: ratesForWidget.usd_to_cny },
              { label: "1 USD = ? USDT", value: ratesForWidget.usd_to_usdt },
            ].map(({ label, value }) => (
              <Col key={label}>
                <span style={{ color: "#888", fontSize: 12 }}>{label}:</span>{" "}
                <b style={{ color: value ? "#222" : "#d9d9d9" }}>{value ?? "—"}</b>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {missingRates.length > 0 && !isLogistics && (
        <Alert
          type="warning"
          style={{ marginBottom: 16 }}
          message={t("order.missing_rate_warning", { currencies: missingRates.join(", "), date: dateStr })}
          action={<Button size="small" onClick={() => setRateModalOpen(true)}>{t("order.add_rate")}</Button>}

          showIcon
        />
      )}

      {isLogistics && !isEdit && clientId && !clientCode && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="У клиента не задан код — в номере накладной будет «XXX»"
          description={<span>Задайте код клиента в разделе <strong>Контрагенты → Редактировать</strong>, затем номер подставится автоматически. Или отредактируйте номер вручную.</span>}
        />
      )}

      {draftAvailable && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={t("draft.restore_prompt")}
          action={
            <Space>
              <Button size="small" type="primary" onClick={handleRestoreDraft}>{t("draft.restore")}</Button>
              <Button size="small" onClick={() => { localStorage.removeItem(DRAFT_KEY); setDraftAvailable(false); }}>{t("draft.discard")}</Button>
            </Space>
          }
        />
      )}

      <Modal
        open={draftModalOpen}
        title={t("draft.unsaved_changes")}
        footer={null}
        onCancel={handleCancelNav}
        destroyOnClose
      >
        <p>{t("draft.leave_warning")}</p>
        <Space style={{ marginTop: 16 }} wrap>
          {!isEdit && <Button type="primary" onClick={handleSaveDraft}>{t("draft.save_draft")}</Button>}
          <Button danger onClick={handleDiscardDraft}>{t("draft.discard_and_leave")}</Button>
          <Button onClick={handleCancelNav}>{t("common.cancel")}</Button>
        </Space>
      </Modal>

      <Form form={form} layout="vertical" onFinish={handleSubmit} onValuesChange={() => { if (!isEdit || formInitializedRef.current) markDirty(); }}>
        {/* Main fields */}
        <Card title={t("order.tab_main")} style={{ marginBottom: 16 }}>
          <Row gutter={16} className="responsive-form">
            <Col span={6}>
              <Form.Item name="order_number" label={t("order.number")} rules={[{ required: true }]}>
                <Input onChange={() => { orderNumberEditedRef.current = true; }} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="order_date" label={t("order.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="client_id" label={t("order.client")} rules={[{ required: true }]}>
                <CounterpartySelect type="client" placeholder={t("order.client")} />
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
            <Col span={5}>
              <Form.Item label={t("order.manager")} tooltip={t("order.manager_readonly_hint")}>
                <Input value={managerName} disabled style={{ color: "#888", background: "#fafafa" }} />
              </Form.Item>
            </Col>
            {clientPhone && (
              <Col span={4}>
                <Form.Item label={t("order.client_phone")}>
                  <Input value={clientPhone} disabled style={{ color: "#555", background: "#fafafa" }} />
                </Form.Item>
              </Col>
            )}
            <Col span={clientPhone ? 15 : 19}>
              <Form.Item name="notes" label={t("order.notes")}>
                <Input.TextArea rows={2} />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item name="excluded_from_accounting" valuePropName="checked">
                <Checkbox>{t("order.excluded_from_accounting")}</Checkbox>
              </Form.Item>
            </Col>
          </Row>
        </Card>

        {/* Logistics: route info */}
        {isLogistics && (
          <Card title={t("order.routing_info")} style={{ marginBottom: 16 }}>
            <Row gutter={16} className="responsive-form">
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
              <Col span={4}>
                <Form.Item
                  name="warehouse_id"
                  label={t("warehouse.shipping_warehouse")}
                  rules={[{ required: true, message: t("warehouse.required_for_logistics") }]}
                >
                  <Select
                    options={(warehouses || []).map((wh: any) => ({ value: wh.id, label: wh.name }))}
                    placeholder={t("warehouse.shipping_warehouse")}
                  />
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
            <LogisticsItemsEditor
              form={form}
              rates={rates}
              savedItemIdByKey={savedItemIdByKey}
              purchasedItemIds={purchasedItemIds}
            />
          ) : (
            <OrderItemsEditor
              form={form}
              rates={rates}
              clientCurrency={clientCurrency}
              pendingPhotos={pendingPhotos}
              onPendingPhotosChange={setPendingPhotos}
              savedItemIdByKey={savedItemIdByKey}
              purchasedItemIds={purchasedItemIds}
            />
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

        {/* Files: pending upload during order creation (any type) */}
        {!isEdit && (
          <Card title={t("order.tab_files")} style={{ marginBottom: 16 }}>
            <Row gutter={8} align="middle" style={{ marginBottom: pendingOrderFiles.length ? 12 : 0 }}>
              <Col>
                <Select
                  value={pendingFileType}
                  onChange={setPendingFileType}
                  style={{ width: 180 }}
                  options={ORDER_FILE_TYPES.map(ft => ({ value: ft.value, label: t(ft.labelKey) }))}
                />
              </Col>
              <Col>
                <Button icon={<UploadOutlined />} onClick={() => pendingFilesInputRef.current?.click()}>
                  {t("order.upload_file")}
                </Button>
                <input
                  ref={pendingFilesInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  style={{ display: "none" }}
                  onChange={async e => {
                    const f = e.target.files?.[0];
                    if (f) {
                      const compressed = await compressImage(f);
                      setPendingOrderFiles(prev => [...prev, { uid: Math.random().toString(36), file: compressed, fileType: pendingFileType }]);
                    }
                    e.target.value = "";
                  }}
                />
              </Col>
              <Col>
                <Text type="secondary" style={{ fontSize: 12 }}>JPEG, PNG, WebP, PDF — max 10 MB</Text>
              </Col>
            </Row>
            {pendingOrderFiles.length > 0 && (
              <Row gutter={[8, 8]}>
                {pendingOrderFiles.map(pf => (
                  <Col key={pf.uid}>
                    <Space size="small" style={{ border: "1px solid #f0f0f0", borderRadius: 4, padding: "4px 8px" }}>
                      <Tag color="blue" style={{ margin: 0 }}>{ORDER_FILE_TYPES.find(f => f.value === pf.fileType) ? t(ORDER_FILE_TYPES.find(f => f.value === pf.fileType)!.labelKey) : pf.fileType}</Tag>
                      <Text style={{ fontSize: 12 }}>{pf.file.name}</Text>
                      <Button size="small" danger icon={<DeleteOutlined />} onClick={() => setPendingOrderFiles(prev => prev.filter(f => f.uid !== pf.uid))} />
                    </Space>
                  </Col>
                ))}
              </Row>
            )}
          </Card>
        )}

        {/* Files section (edit mode only) */}
        {isEdit && (
          <Card title={t("order.cargo_photo")} style={{ marginBottom: 16 }}>
            <OrderFilesTab orderId={id!} />
          </Card>
        )}
      </Form>

      <ExchangeRateForm
        open={rateModalOpen}
        defaultDate={dateStr}
        initialRates={ratesForWidget}
        onClose={() => setRateModalOpen(false)}
      />
    </div>
  );
}
