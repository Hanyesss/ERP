import { useState, useEffect } from "react";
import {
  Modal, Form, InputNumber, Select, DatePicker, Descriptions, Tag, Table,
  Typography, message, Alert, Divider,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import { getCashRegisters } from "../../api/cashRegisters";
import { createPayment } from "../../api/payments";
import type { PaymentPlan } from "../../api/paymentPlans";

const { Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];
const CURRENCY_RANK: Record<string, number> = { USD: 3, USDT: 2, CNY: 1, RUB: 0 };

const fmt = (v?: number | null) =>
  v == null ? "—" : Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

interface Props { plan: PaymentPlan | null; open: boolean; onClose: () => void; }

export default function PlanSettleModal({ plan, open, onClose }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form] = Form.useForm();

  const { data: registers = [] } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then(r => r.data),
    enabled: open,
  });

  const amount: number = Form.useWatch("amount", form) || 0;
  const rateToCny: number = Form.useWatch("rate_to_cny", form) || 1;
  const currency: string = Form.useWatch("currency", form) || "CNY";
  const registerId: string = Form.useWatch("cash_register_id", form);
  const cashRate: number = Form.useWatch("cash_rate", form) || 0;

  const selectedReg = (registers as any[]).find(r => r.id === registerId);
  const regCurrency: string = selectedReg?.currency ?? "CNY";
  const needCashRate = !!registerId && currency !== regCurrency && regCurrency !== "CNY";
  const expRank = CURRENCY_RANK[currency] ?? 1;
  const regRank = CURRENCY_RANK[regCurrency] ?? 1;
  const larger = expRank >= regRank ? currency : regCurrency;
  const smaller = expRank >= regRank ? regCurrency : currency;
  const amountCny = amount * rateToCny;

  useEffect(() => {
    if (open && plan) {
      const hasDeposit = plan.installments.length > 0;
      form.resetFields();
      form.setFieldsValue({
        kind: hasDeposit ? "balance" : "deposit",
        currency: "CNY",
        amount: Number(plan.remaining_cny),
        rate_to_cny: 1,
        payment_date: dayjs(),
      });
    }
  }, [open, plan, form]);

  const settleMut = useMutation({
    mutationFn: (v: any) => {
      if (!plan) throw new Error("no plan");
      const alloc = plan.order_id
        ? { order_id: plan.order_id, amount_cny: amountCny }
        : { purchase_id: plan.purchase_id!, amount_cny: amountCny };
      return createPayment({
        direction: plan.direction,
        counterparty_id: plan.counterparty_id,
        cash_register_id: v.cash_register_id,
        payment_date: v.payment_date.format("YYYY-MM-DD"),
        currency: v.currency,
        amount: v.amount,
        rate_to_cny: v.rate_to_cny,
        allocations: [alloc],
        plan_id: plan.id,
        installment_kind: v.kind,
        cash_rate: needCashRate ? v.cash_rate : undefined,
      } as any);
    },
    onSuccess: () => {
      message.success("✓");
      qc.invalidateQueries({ queryKey: ["payment-plans"] });
      qc.invalidateQueries({ queryKey: ["payments"] });
      onClose();
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const submit = (v: any) => {
    if (needCashRate && (!v.cash_rate || v.cash_rate <= 0)) {
      message.error(t("plan.need_cash_rate")); return;
    }
    settleMut.mutate(v);
  };

  const statusColor: Record<string, string> = { pending: "gold", deposit: "blue", paid: "green" };

  return (
    <Modal
      open={open}
      title={`${t("plan.settle")} · ${plan?.doc_number || plan?.counterparty_name || ""}`}
      onOk={() => form.validateFields().then(submit)}
      onCancel={onClose}
      confirmLoading={settleMut.isPending}
      okText={t("plan.add_installment")}
      cancelText={t("common.close")}
      width={640}
      okButtonProps={{ disabled: plan?.status === "paid" }}
    >
      {plan && (
        <>
          <Descriptions size="small" column={2} bordered style={{ marginBottom: 12 }}>
            <Descriptions.Item label={t("plan.counterparty")}>{plan.counterparty_name}</Descriptions.Item>
            <Descriptions.Item label={t("plan.status")}>
              <Tag color={statusColor[plan.status]}>{t(`plan.status_${plan.status}`)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t("plan.expected")}>{fmt(plan.expected_cny)} CNY</Descriptions.Item>
            <Descriptions.Item label={t("plan.paid")}>{fmt(plan.paid_cny)} CNY</Descriptions.Item>
            <Descriptions.Item label={t("plan.remaining")}>
              <Text strong style={{ color: plan.remaining_cny > 0 ? "#cf1322" : "#3f8600" }}>
                {fmt(plan.remaining_cny)} CNY
              </Text>
            </Descriptions.Item>
          </Descriptions>

          {plan.installments.length > 0 && (
            <Table
              size="small"
              style={{ marginBottom: 12 }}
              pagination={false}
              dataSource={plan.installments}
              rowKey="id"
              columns={[
                { title: t("plan.kind"), dataIndex: "kind", key: "kind",
                  render: (k: string) => k ? t(`plan.kind_${k}`) : "—" },
                { title: t("payment.amount"), key: "amt",
                  render: (_: any, r: any) => `${fmt(r.amount)} ${r.currency}` },
                { title: "CNY", dataIndex: "amount_cny", key: "cny", render: (v: number) => fmt(v) },
                { title: t("payment.date"), dataIndex: "payment_date", key: "d" },
                { title: t("common.created_by"), dataIndex: "created_by_name", key: "who" },
              ]}
            />
          )}

          {plan.status !== "paid" && (
            <>
              <Divider style={{ margin: "8px 0" }}>{t("plan.new_installment")}</Divider>
              <Form form={form} layout="vertical">
                <Form.Item name="kind" label={t("plan.kind")} rules={[{ required: true }]}>
                  <Select options={[
                    { value: "deposit", label: t("plan.kind_deposit") },
                    { value: "balance", label: t("plan.kind_balance") },
                  ]} />
                </Form.Item>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Form.Item name="currency" label={t("payment.currency")} rules={[{ required: true }]}>
                    <Select style={{ width: 100 }} options={CURRENCIES.map(c => ({ value: c, label: c }))} />
                  </Form.Item>
                  <Form.Item name="amount" label={t("payment.amount")} rules={[{ required: true }]}>
                    <InputNumber min={0.01} step={0.01} style={{ width: 150 }} />
                  </Form.Item>
                  <Form.Item name="rate_to_cny" label={t("payment.rate_to_cny")} rules={[{ required: true }]}>
                    <InputNumber min={0.00000001} step={0.01} style={{ width: 140 }} />
                  </Form.Item>
                  <Form.Item label={`${t("payment.amount_cny")} (CNY)`}>
                    <InputNumber disabled value={Number(amountCny.toFixed(2))} style={{ width: 140 }} />
                  </Form.Item>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Form.Item name="cash_register_id" label={t("expense.cash_register")} rules={[{ required: true }]}>
                    <Select style={{ width: 220 }}
                      options={(registers as any[]).filter(r => r.is_active).map(r => ({
                        value: r.id, label: `${r.name} (${r.currency})`,
                      }))} />
                  </Form.Item>
                  <Form.Item name="payment_date" label={t("payment.date")} rules={[{ required: true }]}>
                    <DatePicker style={{ width: 160 }} />
                  </Form.Item>
                </div>
                {needCashRate && (
                  <>
                    <Form.Item name="cash_rate"
                      label={t("expense.cash_rate_label", { larger, smaller })}
                      rules={[{ required: true, message: t("expense.cash_rate_hint") }]}>
                      <InputNumber min={0.000001} step={0.01} precision={6} style={{ width: "100%" }}
                        placeholder={`1 ${larger} = ? ${smaller}`} />
                    </Form.Item>
                    {cashRate > 0 && (
                      <Alert type="info" showIcon style={{ marginBottom: 8 }}
                        message={`${t("expense.cash_deduction")}: ${(expRank > regRank ? amount * cashRate : amount / cashRate).toFixed(6)} ${regCurrency}`} />
                    )}
                  </>
                )}
              </Form>
            </>
          )}
        </>
      )}
    </Modal>
  );
}
