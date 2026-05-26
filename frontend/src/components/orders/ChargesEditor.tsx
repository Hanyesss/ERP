import { Form, InputNumber, Select, Row, Col, Typography } from "antd";
import { useTranslation } from "react-i18next";
import type { FormInstance } from "antd";

const { Text } = Typography;

const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

const CHARGE_TYPES = [
  "delivery",
  "insurance_percent",
  "insurance_cost",
  "china_delivery",
  "extra_packing",
  "loaders",
] as const;

interface Props {
  form: FormInstance;
  rates: Record<string, number>;
}

export default function ChargesEditor({ form, rates }: Props) {
  const { t } = useTranslation();

  return (
    <div>
      <Row gutter={8} style={{ marginBottom: 4 }}>
        <Col span={8}>
          <Text type="secondary" style={{ fontSize: 11 }}>{t("order.cost_breakdown")}</Text>
        </Col>
        <Col span={6}>
          <Text type="secondary" style={{ fontSize: 11 }}>{t("common.amount")}</Text>
        </Col>
        <Col span={4}>
          <Text type="secondary" style={{ fontSize: 11 }}>{t("order.currency")}</Text>
        </Col>
        <Col span={6}>
          <Text type="secondary" style={{ fontSize: 11 }}>CNY</Text>
        </Col>
      </Row>

      {CHARGE_TYPES.map((type, idx) => (
        <ChargeRow key={type} type={type} idx={idx} form={form} rates={rates} />
      ))}

      {/* Hidden charge_type fields */}
      {CHARGE_TYPES.map((type, idx) => (
        <Form.Item
          key={`hidden-${type}`}
          name={["charges", idx, "charge_type"]}
          hidden
          initialValue={type}
        >
          <input />
        </Form.Item>
      ))}
    </div>
  );
}

function ChargeRow({ type, idx, form, rates }: { type: string; idx: number; form: FormInstance; rates: Record<string, number> }) {
  const { t } = useTranslation();
  const watcher = Form.useWatch(["charges", idx], form);
  const amount = Number(watcher?.amount) || 0;
  const currency = watcher?.currency || "USD";
  const rate = rates[currency] ?? null;
  const amountCny = (rate !== null && amount > 0) ? (amount * rate).toFixed(2) : "—";

  return (
    <Row gutter={8} align="middle" style={{ marginBottom: 4 }}>
      <Col span={8}>
        <Text style={{ fontSize: 13 }}>{t(`order.charge_${type}`)}</Text>
      </Col>
      <Col span={6}>
        <Form.Item name={["charges", idx, "amount"]} style={{ margin: 0 }}>
          <InputNumber min={0} precision={2} style={{ width: "100%" }} size="small" placeholder="0" />
        </Form.Item>
      </Col>
      <Col span={4}>
        <Form.Item name={["charges", idx, "currency"]} style={{ margin: 0 }} initialValue="USD">
          <Select size="small" options={CURRENCIES.map(c => ({ value: c, label: c }))} />
        </Form.Item>
      </Col>
      <Col span={6}>
        <Text type={rate === null && amount > 0 ? "danger" : "secondary"} style={{ fontSize: 12 }}>
          {amountCny}
        </Text>
      </Col>
    </Row>
  );
}
