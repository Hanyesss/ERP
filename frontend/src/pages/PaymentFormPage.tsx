import { useEffect, useState, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Form, Input, Select, DatePicker, Button, Card, Typography,
  Space, Row, Col, InputNumber, Radio, Table, Alert, Divider,
  Upload, message, Statistic,
} from "antd";
import { UploadOutlined, FileOutlined } from "@ant-design/icons";
import type { UploadRequestOption } from "rc-upload/lib/interface";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation } from "@tanstack/react-query";
import dayjs from "dayjs";
import { createPayment, uploadPaymentReceipt } from "../api/payments";
import { compressImage } from "../utils/compressImage";
import { getCashRegisters } from "../api/cashRegisters";
import { getOrders } from "../api/orders";
import { getPurchases } from "../api/purchases";
import { getExchangeRates } from "../api/exchangeRates";
import CounterpartySelect from "../components/common/CounterpartySelect";
import type { AllocationInput } from "../types/payment";

const { Title, Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

const fmtCny = (v: number | string) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface AllocRow {
  id: string;
  label: string;
  total_cny: number;
  paid_cny: number;
  remaining_cny: number;
  alloc_amount: number;
}

export default function PaymentFormPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const backUrl = searchParams.get("back") || "/payments";
  const [form] = Form.useForm();
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [counterpartyId, setCounterpartyId] = useState<string | undefined>(
    searchParams.get("counterparty_id") ?? undefined
  );
  const [currency, setCurrency] = useState<string>("CNY");
  const [amount, setAmount] = useState<number>(0);
  const [rateToCny, setRateToCny] = useState<number>(1);
  const [allocRows, setAllocRows] = useState<AllocRow[]>([]);
  const [receiptFile, setReceiptFile] = useState<File | null>(null);

  const paymentDate: dayjs.Dayjs | null = Form.useWatch("payment_date", form);
  const selectedCurrency: string = Form.useWatch("currency", form) || "CNY";
  const dateStr = paymentDate?.format("YYYY-MM-DD");

  useEffect(() => {
    const preselectedCpId = searchParams.get("counterparty_id");
    form.setFieldsValue({
      payment_date: dayjs(),
      currency: "CNY",
      rate_to_cny: 1,
      ...(preselectedCpId ? { counterparty_id: preselectedCpId } : {}),
    });
  }, [form]);

  // Кассы — фильтруем по валюте платежа
  const { data: cashRegisters = [] } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then(r => r.data),
  });
  const cashOptions = cashRegisters
    .filter((r: any) => r.currency === selectedCurrency && r.is_active)
    .map((r: any) => ({ value: r.id, label: `${r.name} (${r.currency})` }));

  // Auto-fetch exchange rate when currency/date changes
  const { data: ratesData } = useQuery({
    queryKey: ["exchange-rates-list"],
    queryFn: () => getExchangeRates({}).then(r => r.data),
  });

  useEffect(() => {
    if (currency === "CNY") {
      setRateToCny(1);
      form.setFieldValue("rate_to_cny", 1);
      return;
    }
    if (!dateStr || !ratesData) return;
    const match = (ratesData.items || ratesData || []).find(
      (r: any) => r.currency === currency && r.rate_date === dateStr
    );
    if (match) {
      const rate = Number(match.rate_to_cny);
      setRateToCny(rate);
      form.setFieldValue("rate_to_cny", rate);
    }
  }, [currency, dateStr, ratesData, form]);

  // Load orders or purchases for counterparty
  const { data: ordersData } = useQuery({
    queryKey: ["orders-for-payment", counterpartyId],
    queryFn: () => getOrders({ client_id: counterpartyId, page_size: 100 }).then(r => r.data),
    enabled: direction === "in" && !!counterpartyId,
  });

  const { data: purchasesData } = useQuery({
    queryKey: ["purchases-for-payment", counterpartyId],
    queryFn: () => getPurchases({ supplier_id: counterpartyId, page_size: 100 }).then(r => r.data),
    enabled: direction === "out" && !!counterpartyId,
  });

  // Build allocation rows when data changes
  useEffect(() => {
    if (direction === "in" && ordersData) {
      const rows = (ordersData.items || [])
        .filter((o: any) => o.payment_status !== "paid")
        .map((o: any) => ({
          id: o.id,
          label: `${o.order_number} — ${o.client_name}`,
          total_cny: Number(o.total_sale_cny),
          paid_cny: 0,
          remaining_cny: Number(o.total_sale_cny),
          alloc_amount: 0,
        }));
      setAllocRows(rows);
    } else if (direction === "out" && purchasesData) {
      const rows = (purchasesData.items || [])
        .filter((p: any) => p.payment_status !== "paid")
        .map((p: any) => ({
          id: p.id,
          label: `${p.purchase_number}`,
          total_cny: Number(p.total_amount_cny),
          paid_cny: 0,
          remaining_cny: Number(p.total_amount_cny),
          alloc_amount: 0,
        }));
      setAllocRows(rows);
    } else {
      setAllocRows([]);
    }
  }, [direction, ordersData, purchasesData, counterpartyId]);

  const amountCny = useMemo(() => {
    return Number((amount * rateToCny).toFixed(2));
  }, [amount, rateToCny]);

  const totalAllocated = useMemo(
    () => allocRows.reduce((sum, r) => sum + r.alloc_amount, 0),
    [allocRows]
  );

  const handleAutoAllocate = () => {
    let remaining = amountCny;
    const updated = allocRows.map(row => {
      if (remaining <= 0) return { ...row, alloc_amount: 0 };
      const toAlloc = Math.min(remaining, row.remaining_cny);
      remaining -= toAlloc;
      return { ...row, alloc_amount: Number(toAlloc.toFixed(2)) };
    });
    setAllocRows(updated);
  };

  const updateAllocAmount = (id: string, value: number) => {
    setAllocRows(rows => rows.map(r => r.id === id ? { ...r, alloc_amount: value } : r));
  };

  const createMutation = useMutation({
    mutationFn: createPayment,
    onSuccess: async (res) => {
      const paymentId = res.data.id;
      if (receiptFile) {
        try {
          await uploadPaymentReceipt(paymentId, receiptFile);
        } catch {
          message.warning(t("payment.receipt_upload") + " — ошибка, загрузите вручную");
        }
      }
      message.success("✓");
      navigate(`/payments/${paymentId}?back=${encodeURIComponent(backUrl)}`);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleSubmit = (values: any) => {
    const allocations: AllocationInput[] = allocRows
      .filter(r => r.alloc_amount > 0)
      .map(r => ({
        [direction === "in" ? "order_id" : "purchase_id"]: r.id,
        amount_cny: r.alloc_amount,
      }));

    if (totalAllocated > amountCny + 0.01) {
      message.error(`Сумма распределений (${fmtCny(totalAllocated)}) превышает сумму платежа (${fmtCny(amountCny)})`);
      return;
    }

    createMutation.mutate({
      direction,
      counterparty_id: values.counterparty_id,
      cash_register_id: values.cash_register_id,
      payment_date: values.payment_date.format("YYYY-MM-DD"),
      currency: values.currency,
      amount: values.amount,
      rate_to_cny: values.rate_to_cny,
      network_fee: values.network_fee || undefined,
      notes: values.notes,
      allocations,
    });
  };

  const missingRate = currency !== "CNY" && rateToCny === 1 && dateStr;

  const allocColumns = [
    {
      title: direction === "in" ? t("payment.alloc_order") : t("payment.alloc_purchase"),
      dataIndex: "label",
      key: "label",
    },
    {
      title: `${t("payment.total")} CNY`,
      dataIndex: "total_cny",
      key: "total",
      align: "right" as const,
      width: 120,
      render: (v: number) => fmtCny(v),
    },
    {
      title: `${t("payment.remaining")} CNY`,
      dataIndex: "remaining_cny",
      key: "remaining",
      align: "right" as const,
      width: 120,
      render: (v: number) => fmtCny(v),
    },
    {
      title: `${t("payment.alloc_amount")} CNY`,
      key: "alloc",
      width: 150,
      render: (_: any, row: AllocRow) => (
        <InputNumber
          size="small"
          min={0}
          value={row.alloc_amount}
          onChange={v => updateAllocAmount(row.id, v ?? 0)}
          style={{ width: "100%" }}
          step={0.01}
        />
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 900 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("payment.create_new")}</Title>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate(backUrl)}>{t("common.cancel")}</Button>
            <Button type="primary" onClick={() => form.submit()} loading={createMutation.isPending}>
              {t("common.save")}
            </Button>
          </Space>
        </Col>
      </Row>

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Card style={{ marginBottom: 16 }}>
          {/* Direction toggle */}
          <Form.Item label={t("payment.direction")}>
            <Radio.Group
              value={direction}
              onChange={e => {
                setDirection(e.target.value);
                setCounterpartyId(undefined);
                form.setFieldValue("counterparty_id", undefined);
                setAllocRows([]);
              }}
              buttonStyle="solid"
            >
              <Radio.Button value="in">{t("payment.direction_in")}</Radio.Button>
              <Radio.Button value="out">{t("payment.direction_out")}</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="payment_date" label={t("payment.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="counterparty_id" label={t("payment.counterparty")} rules={[{ required: true }]}>
                <CounterpartySelect
                  type={direction === "in" ? "client" : "supplier"}
                  placeholder={t("payment.counterparty")}
                  onChange={(v) => {
                    setCounterpartyId(v);
                    setAllocRows([]);
                  }}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="currency" label={t("payment.currency")} rules={[{ required: true }]}>
                <Select
                  options={CURRENCIES.map(c => ({ value: c, label: c }))}
                  onChange={(v) => { setCurrency(v); form.setFieldValue("cash_register_id", undefined); }}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="cash_register_id"
                label={t("cash.register")}
                rules={[{ required: true, message: t("cash.select_register") }]}
              >
                <Select
                  options={cashOptions}
                  placeholder={t("cash.select_register")}
                  notFoundContent={<span style={{ color: "#aaa" }}>Нет касс с валютой {selectedCurrency}</span>}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="amount" label={t("payment.amount")} rules={[{ required: true }]}>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={0.01}
                  onChange={v => setAmount(v ?? 0)}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="rate_to_cny" label={t("payment.rate_to_cny")} rules={[{ required: true }]}>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={0.00001}
                  precision={8}
                  disabled={currency === "CNY"}
                  onChange={v => setRateToCny(v ?? 1)}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label={`${t("payment.amount_cny")} (CNY)`}>
                <InputNumber
                  style={{ width: "100%" }}
                  value={amountCny}
                  disabled
                />
              </Form.Item>
            </Col>
          </Row>

          {currency === "USDT" && (
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item name="network_fee" label={t("payment.network_fee")}>
                  <InputNumber style={{ width: "100%" }} min={0} step={0.01} />
                </Form.Item>
              </Col>
            </Row>
          )}

          {missingRate && (
            <Alert
              type="warning"
              showIcon
              message={`Нет курса ${currency} на ${dateStr}. Введите курс вручную или добавьте в разделе «Курсы валют».`}
              style={{ marginBottom: 16 }}
            />
          )}

          <Form.Item name="notes" label={t("payment.notes")}>
            <Input.TextArea rows={2} />
          </Form.Item>

          <Form.Item label={t("payment.receipt")}>
            <Space direction="vertical">
              <Upload
                customRequest={async ({ file }: UploadRequestOption) => {
                  const compressed = await compressImage(file as File);
                  setReceiptFile(compressed);
                }}
                showUploadList={false}
                maxCount={1}
                accept=".jpg,.jpeg,.png,.webp,.pdf"
              >
                <Button icon={<UploadOutlined />}>
                  {receiptFile ? t("payment.receipt_replace") : t("payment.receipt_upload")}
                </Button>
              </Upload>
              {receiptFile && (() => {
                const isPdf = receiptFile.type === "application/pdf";
                return isPdf ? (
                  <Space>
                    <FileOutlined style={{ fontSize: 24, color: "#ff4d4f" }} />
                    <span>{receiptFile.name}</span>
                    <Button size="small" danger onClick={() => setReceiptFile(null)}>✕</Button>
                  </Space>
                ) : (
                  <div style={{ position: "relative", display: "inline-block" }}>
                    <img
                      src={URL.createObjectURL(receiptFile)}
                      alt="receipt preview"
                      style={{ maxWidth: 300, maxHeight: 300, borderRadius: 6, border: "1px solid #f0f0f0" }}
                    />
                    <Button
                      size="small"
                      danger
                      style={{ position: "absolute", top: 4, right: 4 }}
                      onClick={() => setReceiptFile(null)}
                    >✕</Button>
                  </div>
                );
              })()}
            </Space>
          </Form.Item>
        </Card>

        {/* Allocations */}
        {counterpartyId && allocRows.length > 0 && (
          <Card
            title={t("payment.allocations")}
            extra={
              <Button size="small" onClick={handleAutoAllocate}>
                {t("payment.allocate_auto")}
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            <Table scroll={{ x: "max-content" }}
              dataSource={allocRows}
              rowKey="id"
              size="small"
              pagination={false}
              columns={allocColumns}
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} colSpan={3} align="right">
                    <strong>{t("payment.allocated")}: {fmtCny(totalAllocated)} / {fmtCny(amountCny)} CNY</strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right">
                    <strong
                      style={{ color: totalAllocated > amountCny ? "#cf1322" : "#389e0d" }}
                    >
                      {totalAllocated > amountCny ? "⚠ превышение" : `остаток: ${fmtCny(amountCny - totalAllocated)}`}
                    </strong>
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              )}
            />
          </Card>
        )}

        {counterpartyId && allocRows.length === 0 && (
          <Card style={{ marginBottom: 16 }}>
            <Text type="secondary">
              {direction === "in"
                ? "Нет неоплаченных заказов для этого клиента. Платёж будет сохранён как аванс."
                : "Нет неоплаченных закупок для этого поставщика. Платёж будет сохранён как аванс."}
            </Text>
          </Card>
        )}
      </Form>
    </div>
  );
}
