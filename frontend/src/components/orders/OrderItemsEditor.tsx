import { Form, Input, InputNumber, Select, Button, Row, Col, Typography, Divider } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import type { FormInstance } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getCounterparties } from "../../api/counterparties";

const { Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT"];

interface Props {
  form: FormInstance;
  rates: Record<string, number>;
  clientCurrency: string;
}

export default function OrderItemsEditor({ form, rates, clientCurrency }: Props) {
  const { t } = useTranslation();

  const { data: suppliers } = useQuery({
    queryKey: ["counterparties-suppliers"],
    queryFn: () => getCounterparties({ type: "supplier", page_size: 200 }).then(r => r.data),
  });

  const supplierOptions = (suppliers?.items || []).map(s => ({ value: s.id, label: s.name }));

  return (
    <Form.List name="items">
      {(fields, { add, remove }) => (
        <div>
          {/* Header row */}
          <Row gutter={4} style={{ marginBottom: 4, paddingLeft: 4 }}>
            {[
              [t("order.item_name"), 4],
              [t("order.item_quantity"), 2],
              [t("order.item_unit"), 2],
              [t("order.item_supplier"), 4],
              [t("order.item_cost_price"), 2],
              [t("order.item_cost_currency"), 2],
              [t("order.item_sale_price"), 2],
              [t("order.item_sale_currency"), 2],
              ["", 2],
            ].map(([label, span], i) => (
              <Col key={i} span={span as number}>
                <Text type="secondary" style={{ fontSize: 11 }}>{label}</Text>
              </Col>
            ))}
          </Row>

          {fields.map(({ key, name }) => (
            <Row key={key} gutter={4} align="top" style={{ marginBottom: 4 }}>
              <Col span={4}>
                <Form.Item name={[name, "name"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
                  <Input size="small" placeholder={t("order.item_name")} />
                </Form.Item>
              </Col>
              <Col span={2}>
                <Form.Item name={[name, "quantity"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
                  <InputNumber size="small" min={0} style={{ width: "100%" }} placeholder="0" />
                </Form.Item>
              </Col>
              <Col span={2}>
                <Form.Item name={[name, "unit"]} style={{ margin: 0 }}>
                  <Input size="small" placeholder="шт" />
                </Form.Item>
              </Col>
              <Col span={4}>
                <Form.Item name={[name, "supplier_id"]} style={{ margin: 0 }}>
                  <Select size="small" allowClear options={supplierOptions} showSearch
                    filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())}
                    placeholder={t("order.item_supplier")} />
                </Form.Item>
              </Col>
              <Col span={2}>
                <Form.Item name={[name, "cost_price"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
                  <InputNumber size="small" min={0} style={{ width: "100%" }} placeholder="0" />
                </Form.Item>
              </Col>
              <Col span={2}>
                <Form.Item name={[name, "cost_currency"]} style={{ margin: 0 }}
                  initialValue="CNY">
                  <Select size="small" options={CURRENCIES.map(c => ({ value: c, label: c }))} />
                </Form.Item>
              </Col>
              <Col span={2}>
                <Form.Item name={[name, "sale_price"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
                  <InputNumber size="small" min={0} style={{ width: "100%" }} placeholder="0" />
                </Form.Item>
              </Col>
              <Col span={2}>
                <Form.Item name={[name, "sale_currency"]} style={{ margin: 0 }}
                  initialValue={clientCurrency || "CNY"}>
                  <Select size="small" options={CURRENCIES.map(c => ({ value: c, label: c }))} />
                </Form.Item>
              </Col>
              <Col span={2}>
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => remove(name)} />
              </Col>
            </Row>
          ))}

          <Button type="dashed" icon={<PlusOutlined />} onClick={() => add({ cost_currency: "CNY", sale_currency: clientCurrency || "CNY" })}
            style={{ width: "100%", marginTop: 8 }}>
            {t("order.add_item")}
          </Button>
        </div>
      )}
    </Form.List>
  );
}
