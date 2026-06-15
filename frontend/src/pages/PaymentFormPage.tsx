import { useEffect, useState, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Form, Input, Select, DatePicker, Button, Card, Typography,
  Space, Row, Col, InputNumber, Radio, Table, Alert, Divider,
  Upload, message, Statistic, Modal, Checkbox,
} from "antd";
import { UploadOutlined, FileOutlined } from "@ant-design/icons";
import type { UploadRequestOption } from "rc-upload/lib/interface";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation } from "@tanstack/react-query";
import dayjs from "dayjs";
import { createPayment, uploadPaymentReceipt, getCounterpartyBalance, addAllocations, type CounterpartyBalanceData } from "../api/payments";
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
  order_number?: string;
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
  const [receiptFiles, setReceiptFiles] = useState<File[]>([]);
  const [distributeOpen, setDistributeOpen] = useState(false);
  const [distributePaymentId, setDistributePaymentId] = useState<string | undefined>();
  const [distributeOrderId, setDistributeOrderId] = useState<string | undefined>();
  const [distributeAmount, setDistributeAmount] = useState<number>(0);
  const [distributing, setDistributing] = useState(false);
  const [useClientBalance, setUseClientBalance] = useState(false);
  const [debitRegisterId, setDebitRegisterId] = useState<string | undefined>();
  const [balanceRate, setBalanceRate] = useState<number>(1);

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

  const { data: counterpartyBalance } = useQuery({
    queryKey: ["counterparty-balance", counterpartyId],
    queryFn: () => getCounterpartyBalance(counterpartyId!).then(r => r.data),
    enabled: direction === "in" && !!counterpartyId,
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
          paid_cny: Number(o.paid_amount_cny ?? 0),
          remaining_cny: Number(o.remaining_amount_cny ?? o.total_sale_cny),
          alloc_amount: 0,
        }));
      setAllocRows(rows);
    } else if (direction === "out" && purchasesData) {
      const rows = (purchasesData.items || [])
        .filter((p: any) => p.payment_status !== "paid")
        .map((p: any) => ({
          id: p.id,
          label: `${p.purchase_number}`,
          order_number: p.order_number || undefined,
          total_cny: Number(p.total_amount_cny),
          paid_cny: Number(p.paid_amount_cny ?? 0),
          remaining_cny: Number(p.remaining_amount_cny ?? p.total_amount_cny),
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

  // When using client balance: pick the payment and derive debit register currency
  const selectedUnallocatedPay = useMemo(() => {
    if (!counterpartyBalance?.unallocated_payments) return null;
    return counterpartyBalance.unallocated_payments[0] ?? null;
  }, [counterpartyBalance]);

  const debitRegCurrency = useMemo(() => {
    if (!debitRegisterId) return null;
    const cr = cashRegisters.find((r: any) => r.id === debitRegisterId);
    return cr?.currency ?? null;
  }, [debitRegisterId, cashRegisters]);

  const debitRegOptions = useMemo(() => {
    return (cashRegisters as any[]).filter(r => r.is_active).map((r: any) => ({
      value: r.id,
      label: `${r.name} (${r.currency})`,
    }));
  }, [cashRegisters]);

  const handleDistribute = async () => {
    if (!distributePaymentId || !distributeOrderId || distributeAmount <= 0) return;
    setDistributing(true);
    try {
      await addAllocations(distributePaymentId, [{ order_id: distributeOrderId, amount_cny: distributeAmount }]);
      message.success("✓");
      setDistributeOpen(false);
      // Refresh orders data
      setAllocRows(rows => rows.map(r => r.id === distributeOrderId
        ? { ...r, paid_cny: r.paid_cny + distributeAmount, remaining_cny: Math.max(r.remaining_cny - distributeAmount, 0) }
        : r
      ));
    } catch (e: any) {
      message.error(e.response?.data?.detail || "Error");
    } finally {
      setDistributing(false);
    }
  };

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
      for (const file of receiptFiles) {
        try {
          await uploadPaymentReceipt(paymentId, file);
        } catch {
          message.warning(`${file.name} — ошибка загрузки, добавьте вручную`);
        }
      }
      message.success("✓");
      navigate(`/payments/${paymentId}?back=${encodeURIComponent(backUrl)}`);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleSubmit = async (values: any) => {
    const allocations: AllocationInput[] = allocRows
      .filter(r => r.alloc_amount > 0)
      .map(r => ({
        [direction === "in" ? "order_id" : "purchase_id"]: r.id,
        amount_cny: r.alloc_amount,
      }));

    // "Use client balance" mode: allocate from existing payment, don't create new one
    if (useClientBalance && direction === "in") {
      if (!selectedUnallocatedPay) {
        message.error("Нет нераспределённого остатка");
        return;
      }
      if (allocations.length === 0) {
        message.error("Выберите заказ(ы) для распределения");
        return;
      }
      const totalToAlloc = allocations.reduce((s, a) => s + Number(a.amount_cny), 0);
      if (totalToAlloc > Number(selectedUnallocatedPay.unallocated_cny) + 0.01) {
        message.error(`Сумма распределений (${fmtCny(totalToAlloc)}) превышает остаток (${fmtCny(Number(selectedUnallocatedPay.unallocated_cny))})`);
        return;
      }
      try {
        await addAllocations(selectedUnallocatedPay.payment_id, allocations);
        message.success("✓");
        navigate(backUrl);
      } catch (e: any) {
        message.error(e.response?.data?.detail || "Error");
      }
      return;
    }

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
    ...(direction === "out" ? [{
      title: t("payment.alloc_order_num"),
      dataIndex: "order_number",
      key: "order_num",
      render: (v: string | undefined) => v || "—",
    }] : []),
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

          {!useClientBalance && (
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  name="cash_register_id"
                  label={t("cash.register")}
                  rules={[{ required: !useClientBalance, message: t("cash.select_register") }]}
                >
                  <Select
                    options={cashOptions}
                    placeholder={t("cash.select_register")}
                    notFoundContent={<span style={{ color: "#aaa" }}>Нет касс с валютой {selectedCurrency}</span>}
                  />
                </Form.Item>
              </Col>
            </Row>
          )}

          {!useClientBalance && (
            <>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="amount" label={t("payment.amount")} rules={[{ required: !useClientBalance }]}>
                    <InputNumber
                      style={{ width: "100%" }}
                      min={0}
                      step={0.01}
                      onChange={v => setAmount(v ?? 0)}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="rate_to_cny" label={t("payment.rate_to_cny")} rules={[{ required: !useClientBalance }]}>
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
                    <InputNumber style={{ width: "100%" }} value={amountCny} disabled />
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
            </>
          )}

          {/* Use client balance: debit register + optional rate */}
          {useClientBalance && direction === "in" && (
            <>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label={t("payment.debit_register")} required>
                    <Select
                      options={debitRegOptions}
                      placeholder={t("cash.select_register")}
                      value={debitRegisterId}
                      onChange={v => { setDebitRegisterId(v); setBalanceRate(1); }}
                    />
                  </Form.Item>
                </Col>
                {debitRegCurrency && debitRegCurrency !== "CNY" && (
                  <Col span={12}>
                    <Form.Item label={`${t("payment.rate_to_cny")} (${debitRegCurrency} → CNY)`} required>
                      <InputNumber
                        style={{ width: "100%" }}
                        min={0}
                        step={0.00001}
                        precision={8}
                        value={balanceRate}
                        onChange={v => setBalanceRate(v ?? 1)}
                      />
                    </Form.Item>
                  </Col>
                )}
              </Row>
              {selectedUnallocatedPay && (
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 12 }}
                  message={`${t("payment.from_payment")}: ${selectedUnallocatedPay.payment_date} ${fmtCny(Number(selectedUnallocatedPay.unallocated_cny))} CNY`}
                />
              )}
            </>
          )}

          <Form.Item name="notes" label={t("payment.notes")}>
            <Input.TextArea rows={2} />
          </Form.Item>

          {!useClientBalance && (
          <Form.Item label={t("payment.receipt")}>
            <Space direction="vertical" style={{ width: "100%" }}>
              {receiptFiles.length < 10 && (
                <Upload
                  customRequest={async ({ file }: UploadRequestOption) => {
                    const compressed = await compressImage(file as File);
                    setReceiptFiles(prev => [...prev, compressed]);
                  }}
                  showUploadList={false}
                  accept=".jpg,.jpeg,.png,.webp,.pdf"
                >
                  <Button icon={<UploadOutlined />}>
                    {t("payment.receipt_upload")}
                  </Button>
                </Upload>
              )}
              {receiptFiles.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 4 }}>
                  {receiptFiles.map((file, idx) => {
                    const isPdf = file.type === "application/pdf";
                    return (
                      <div key={idx} style={{ position: "relative", border: "1px solid #f0f0f0", borderRadius: 6, padding: 4 }}>
                        {isPdf ? (
                          <Space style={{ padding: "4px 8px" }}>
                            <FileOutlined style={{ fontSize: 20, color: "#ff4d4f" }} />
                            <span style={{ fontSize: 12, maxWidth: 80, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {file.name}
                            </span>
                          </Space>
                        ) : (
                          <img
                            src={URL.createObjectURL(file)}
                            alt="preview"
                            style={{ width: 80, height: 80, objectFit: "cover", borderRadius: 4, display: "block" }}
                          />
                        )}
                        <Button
                          size="small"
                          danger
                          style={{ position: "absolute", top: 2, right: 2, minWidth: 20, padding: "0 3px", fontSize: 10 }}
                          onClick={() => setReceiptFiles(prev => prev.filter((_, i) => i !== idx))}
                        >✕</Button>
                      </div>
                    );
                  })}
                </div>
              )}
              {receiptFiles.length > 0 && (
                <span style={{ color: "#999", fontSize: 12 }}>{receiptFiles.length} / 10</span>
              )}
            </Space>
          </Form.Item>
          )}
        </Card>

        {/* Unallocated balance warning + distribute button + use-balance checkbox */}
        {direction === "in" && counterpartyBalance && Number(counterpartyBalance.unallocated_cny) > 0 && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message={t("payment.unallocated_balance_warning", {
              amount: fmtCny(Number(counterpartyBalance.unallocated_cny)),
            })}
          />
        )}

        {/* Use client balance checkbox */}
        {direction === "in" && counterpartyBalance && Number(counterpartyBalance.unallocated_cny) > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Checkbox
              checked={useClientBalance}
              onChange={e => {
                setUseClientBalance(e.target.checked);
                setDebitRegisterId(undefined);
                setBalanceRate(1);
              }}
            >
              {t("payment.use_client_balance")}
            </Checkbox>
          </div>
        )}

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
                  <Table.Summary.Cell index={0} colSpan={direction === "out" ? 4 : 3} align="right">
                    <strong>
                      {t("payment.allocated")}: {fmtCny(totalAllocated)} / {fmtCny(useClientBalance ? Number(selectedUnallocatedPay?.unallocated_cny ?? 0) : amountCny)} CNY
                    </strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={direction === "out" ? 4 : 3} align="right">
                    <strong
                      style={{ color: totalAllocated > (useClientBalance ? Number(selectedUnallocatedPay?.unallocated_cny ?? 0) : amountCny) ? "#cf1322" : "#389e0d" }}
                    >
                      {(() => {
                        const cap = useClientBalance ? Number(selectedUnallocatedPay?.unallocated_cny ?? 0) : amountCny;
                        return totalAllocated > cap
                          ? t("payment.over_budget")
                          : `${t("payment.remaining_label")}: ${fmtCny(cap - totalAllocated)}`;
                      })()}
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

      {/* Distribute existing balance modal */}
      <Modal
        open={distributeOpen}
        title={t("payment.distribute_balance")}
        onCancel={() => setDistributeOpen(false)}
        onOk={handleDistribute}
        okText={t("payment.distribute_confirm")}
        confirmLoading={distributing}
        okButtonProps={{ disabled: !distributePaymentId || !distributeOrderId || distributeAmount <= 0 }}
      >
        {counterpartyBalance && counterpartyBalance.unallocated_payments.length > 1 && (
          <Form.Item label={t("payment.select_payment")} style={{ marginBottom: 12 }}>
            <Select
              value={distributePaymentId}
              onChange={v => setDistributePaymentId(v)}
              options={counterpartyBalance.unallocated_payments.map(p => ({
                value: p.payment_id,
                label: `${p.payment_date} — ${fmtCny(Number(p.unallocated_cny))} CNY`,
              }))}
            />
          </Form.Item>
        )}
        {counterpartyBalance && counterpartyBalance.unallocated_payments.length === 1 && (
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary">
              {t("payment.from_payment")}: {counterpartyBalance.unallocated_payments[0].payment_date} ({fmtCny(Number(counterpartyBalance.unallocated_payments[0].unallocated_cny))} CNY)
            </Text>
          </div>
        )}
        <Form.Item label={t("order.order")} style={{ marginBottom: 12 }}>
          <Select
            value={distributeOrderId}
            onChange={v => {
              setDistributeOrderId(v);
              const row = allocRows.find(r => r.id === v);
              const pay = counterpartyBalance?.unallocated_payments.find(p => p.payment_id === distributePaymentId);
              if (row && pay) {
                setDistributeAmount(Number(Math.min(row.remaining_cny, Number(pay.unallocated_cny)).toFixed(2)));
              }
            }}
            options={allocRows.filter(r => r.remaining_cny > 0).map(r => ({
              value: r.id,
              label: `${r.label} (${t("payment.remaining")}: ${fmtCny(r.remaining_cny)} CNY)`,
            }))}
            placeholder={t("payment.select_order")}
          />
        </Form.Item>
        <Form.Item label={`${t("payment.amount")} CNY`} style={{ marginBottom: 0 }}>
          <InputNumber
            value={distributeAmount}
            onChange={v => setDistributeAmount(Number(v) || 0)}
            min={0.01}
            max={(() => {
              const row = allocRows.find(r => r.id === distributeOrderId);
              const pay = counterpartyBalance?.unallocated_payments.find(p => p.payment_id === distributePaymentId);
              return Math.min(row?.remaining_cny ?? 999999, Number(pay?.unallocated_cny ?? 999999));
            })()}
            precision={2}
            style={{ width: "100%" }}
          />
        </Form.Item>
      </Modal>
    </div>
  );
}
