import { Form, InputNumber, Select, Row, Col, Divider, Typography } from "antd";
import type { FormInstance } from "antd";
import { useTranslation } from "react-i18next";

const { Text } = Typography;
const CURRENCIES = ["CNY", "USD", "RUB", "USDT"];

/**
 * Обмен валют: сумма + валюта закупа/продажи + курсы. Прибыль считается автоматически:
 * прибыль = сумма × (курс продажи − курс закупа), в валюте продажи. Без позиций и закупок.
 */
export default function ExchangeEditor({ form }: { form: FormInstance }) {
  const { t } = useTranslation();
  const amount: number = Form.useWatch("exchange_amount", form) || 0;
  const buyRate: number = Form.useWatch("exchange_buy_rate", form) || 0;
  const sellRate: number = Form.useWatch("exchange_sell_rate", form) || 0;
  const sellCur: string = Form.useWatch("exchange_sell_currency", form) || "";

  const profit = Number((amount * (sellRate - buyRate)).toFixed(2));

  return (
    <>
      <Row gutter={16} className="responsive-form">
        <Col xs={24} sm={8}>
          <Form.Item name="exchange_amount" label={t("order.exchange_amount")} rules={[{ required: true }]}>
            <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
        <Col xs={12} sm={8}>
          <Form.Item name="exchange_buy_currency" label={t("order.exchange_buy_currency")} rules={[{ required: true }]} initialValue="USD">
            <Select options={CURRENCIES.map(c => ({ value: c, label: c }))} />
          </Form.Item>
        </Col>
        <Col xs={12} sm={8}>
          <Form.Item name="exchange_sell_currency" label={t("order.exchange_sell_currency")} rules={[{ required: true }]} initialValue="RUB">
            <Select options={CURRENCIES.map(c => ({ value: c, label: c }))} />
          </Form.Item>
        </Col>
        <Col xs={12} sm={8}>
          <Form.Item name="exchange_buy_rate" label={t("order.exchange_buy_rate")} rules={[{ required: true }]}>
            <InputNumber min={0} step={0.0001} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
        <Col xs={12} sm={8}>
          <Form.Item name="exchange_sell_rate" label={t("order.exchange_sell_rate")} rules={[{ required: true }]}>
            <InputNumber min={0} step={0.0001} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
      </Row>
      <Divider style={{ margin: "8px 0 12px" }} />
      <Row justify="end">
        <Col>
          <Text style={{ fontSize: 15 }}>
            {t("order.exchange_profit")}:{" "}
            <Text strong type={profit >= 0 ? "success" : "danger"} style={{ fontSize: 18 }}>
              {profit.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} {sellCur}
            </Text>
          </Text>
        </Col>
      </Row>
    </>
  );
}
