import { useEffect } from "react";
import { Modal, Form, Select, InputNumber, DatePicker, message } from "antd";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { createExchangeRate } from "../../api/exchangeRates";

interface Props {
  open: boolean;
  defaultDate?: string;
  onClose: () => void;
}

export default function ExchangeRateForm({ open, defaultDate, onClose }: Props) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const qc = useQueryClient();

  useEffect(() => {
    if (open) {
      form.resetFields();
      if (defaultDate) form.setFieldValue("rate_date", dayjs(defaultDate));
    }
  }, [open, defaultDate, form]);

  const mutation = useMutation({
    mutationFn: (values: any) =>
      createExchangeRate({
        currency: values.currency,
        rate_to_cny: values.rate_to_cny,
        rate_date: values.rate_date.format("YYYY-MM-DD"),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exchange-rates"] });
      qc.invalidateQueries({ queryKey: ["exchange-rates-check"] });
      message.success(t("common.save") + " ✓");
      onClose();
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail || "";
      if (detail.includes("already exists")) {
        message.error(t("exchange_rate.already_exists", { currency: "", date: "" }));
      } else {
        message.error(detail || "Error");
      }
    },
  });

  return (
    <Modal
      title={t("exchange_rate.add_new")}
      open={open}
      onOk={() => form.validateFields().then(v => mutation.mutate(v))}
      onCancel={onClose}
      okText={t("common.save")}
      cancelText={t("common.cancel")}
      confirmLoading={mutation.isPending}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item name="currency" label={t("exchange_rate.currency")} rules={[{ required: true }]}>
          <Select options={[{ value: "RUB", label: "RUB" }, { value: "USDT", label: "USDT" }]} />
        </Form.Item>
        <Form.Item name="rate_to_cny" label={t("exchange_rate.rate")} rules={[{ required: true }]}>
          <InputNumber min={0} precision={8} step={0.001} style={{ width: "100%" }} placeholder="0.085" />
        </Form.Item>
        <Form.Item name="rate_date" label={t("exchange_rate.date")} rules={[{ required: true }]}>
          <DatePicker style={{ width: "100%" }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
