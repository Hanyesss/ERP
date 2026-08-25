import { Form, Input, InputNumber, Select, Row, Col } from "antd";
import { useTranslation } from "react-i18next";

const CURRENCIES = ["CNY", "USD", "RUB", "USDT"];

/**
 * Упрощённый редактор для вида деятельности «Сервис»:
 * одна строка — описание услуги + сумма + валюта. Без закупки и списка позиций.
 * Пишет в form.items[0] (quantity=1), чтобы итоги/сабмит работали как обычно.
 */
export default function ServiceItemEditor({ clientCurrency }: { clientCurrency?: string }) {
  const { t } = useTranslation();
  return (
    <>
      <Form.Item name={["items", 0, "id"]} hidden><Input /></Form.Item>
      <Form.Item name={["items", 0, "quantity"]} initialValue={1} hidden><InputNumber /></Form.Item>
      <Row gutter={12} align="bottom" className="responsive-form">
        <Col flex="auto">
          <Form.Item
            name={["items", 0, "name"]}
            label={t("order.service_description")}
            rules={[{ required: true, message: "" }]}
          >
            <Input.TextArea autoSize={{ minRows: 1, maxRows: 4 }} placeholder={t("order.service_description")} />
          </Form.Item>
        </Col>
        <Col>
          <Form.Item
            name={["items", 0, "sale_price"]}
            label={t("order.service_amount")}
            rules={[{ required: true, message: "" }]}
          >
            <InputNumber min={0} step={0.01} style={{ width: 170 }} />
          </Form.Item>
        </Col>
        <Col>
          <Form.Item
            name={["items", 0, "sale_currency"]}
            label={t("payment.currency")}
            initialValue={clientCurrency || "CNY"}
          >
            <Select options={CURRENCIES.map((c) => ({ value: c, label: c }))} style={{ width: 100 }} />
          </Form.Item>
        </Col>
      </Row>
    </>
  );
}
