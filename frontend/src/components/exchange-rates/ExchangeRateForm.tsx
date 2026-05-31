import { useEffect } from "react";
import { Modal, Form, InputNumber, DatePicker, Row, Col } from "antd";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { upsertExchangeRate } from "../../api/exchangeRates";

interface Props {
  open: boolean;
  defaultDate?: string;
  initialRates?: {
    cny_to_rub?: number;
    usd_to_rub?: number;
    usd_to_cny?: number;
    usd_to_usdt?: number;
  };
  onClose: () => void;
}

export default function ExchangeRateForm({ open, defaultDate, initialRates, onClose }: Props) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const qc = useQueryClient();

  useEffect(() => {
    if (open) {
      form.resetFields();
      form.setFieldsValue({
        rate_date: dayjs(defaultDate || dayjs().format("YYYY-MM-DD")),
        cny_to_rub: initialRates?.cny_to_rub,
        usd_to_rub: initialRates?.usd_to_rub,
        usd_to_cny: initialRates?.usd_to_cny,
        usd_to_usdt: initialRates?.usd_to_usdt,
      });
    }
  }, [open, defaultDate, initialRates, form]);

  const mutation = useMutation({
    mutationFn: async (values: any) => {
      const dateStr: string = values.rate_date.format("YYYY-MM-DD");
      // 1 RUB = (1 / cny_to_rub) CNY
      const rubRateToCny = 1 / values.cny_to_rub;
      // 1 USD = usd_to_cny CNY
      const usdRateToCny = values.usd_to_cny;
      // 1 USDT = usd_to_cny / usd_to_usdt CNY
      const usdtRateToCny = values.usd_to_cny / values.usd_to_usdt;

      await Promise.all([
        upsertExchangeRate({ currency: "RUB", rate_to_cny: rubRateToCny, rate_date: dateStr }),
        upsertExchangeRate({ currency: "USD", rate_to_cny: usdRateToCny, rate_date: dateStr }),
        upsertExchangeRate({ currency: "USDT", rate_to_cny: usdtRateToCny, rate_date: dateStr }),
      ]);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exchange-rates"] });
      qc.invalidateQueries({ queryKey: ["exchange-rates-check"] });
      onClose();
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
        <Form.Item name="rate_date" label={t("exchange_rate.date")} rules={[{ required: true }]}>
          <DatePicker style={{ width: "100%" }} />
        </Form.Item>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="cny_to_rub" label="1 CNY = ? RUB" rules={[{ required: true }, { type: "number", min: 0.0001 }]}>
              <InputNumber min={0} precision={4} step={0.1} style={{ width: "100%" }} placeholder="11.50" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="usd_to_rub" label="1 USD = ? RUB" rules={[{ required: true }, { type: "number", min: 0.0001 }]}>
              <InputNumber min={0} precision={4} step={1} style={{ width: "100%" }} placeholder="85.00" />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item name="usd_to_cny" label="1 USD = ? CNY" rules={[{ required: true }, { type: "number", min: 0.0001 }]}>
              <InputNumber min={0} precision={4} step={0.01} style={{ width: "100%" }} placeholder="7.25" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="usd_to_usdt" label="1 USD = ? USDT" rules={[{ required: true }, { type: "number", min: 0.0001 }]}>
              <InputNumber min={0} precision={4} step={0.01} style={{ width: "100%" }} placeholder="1.02" />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Modal>
  );
}
