import { useMemo } from "react";
import { Form, Input, InputNumber, Select, Button, Row, Col, Typography, Tooltip } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import type { FormInstance } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getCounterparties } from "../../api/counterparties";

const { Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

interface Props {
  form: FormInstance;
  rates: Record<string, number>;
  savedItemIdByKey?: Record<number, string>;
  purchasedItemIds?: Set<string>;
}

export default function LogisticsItemsEditor({ form, rates, savedItemIdByKey = {}, purchasedItemIds }: Props) {
  const { t } = useTranslation();

  const { data: suppliers } = useQuery({
    queryKey: ["counterparties-suppliers"],
    queryFn: () => getCounterparties({ type: "supplier", page_size: 200 }).then(r => r.data),
  });

  const supplierOptions = (suppliers?.items || []).map(s => ({ value: s.id, label: s.name }));

  return (
    <Form.List name="items">
      {(fields, { add, remove }) => (
        <div className="mobile-scroll-x">
          {/* Header */}
          <Row gutter={4} style={{ marginBottom: 4 }}>
            {[
              [t("order.item_name"), 5],
              [t("order.weight_kg"), 2],
              [t("order.volume_m3"), 2],
              [t("order.density"), 2],
              [t("order.price_per_kg"), 3],
              [t("order.cargo_value"), 3],
              [t("order.item_supplier"), 4],
              [t("order.places_count"), 2],
              ["", 1],
            ].map(([label, span], i) => (
              <Col key={i} span={span as number}>
                <Text type="secondary" style={{ fontSize: 11 }}>{label}</Text>
              </Col>
            ))}
          </Row>

          {fields.map(({ key, name }) => {
            const savedItemId = savedItemIdByKey[key];
            const isPurchased = !!(savedItemId && purchasedItemIds?.has(savedItemId));
            return (
              <LogisticsItemRow key={key} name={name} remove={remove} form={form}
                rates={rates} supplierOptions={supplierOptions} isPurchased={isPurchased} />
            );
          })}

          <Button
            type="dashed" icon={<PlusOutlined />}
            onClick={() => add({ price_per_kg_currency: "USD", cargo_value_currency: "USD" })}
            style={{ width: "100%", marginTop: 8 }}
          >
            {t("order.add_item")}
          </Button>
        </div>
      )}
    </Form.List>
  );
}

function LogisticsItemRow({ name, remove, form, rates, supplierOptions, isPurchased }: any) {
  const { t } = useTranslation();

  // Compute density from form values
  const watcher = Form.useWatch(["items", name], form);
  const density = useMemo(() => {
    const wkg = Number(watcher?.weight_kg);
    const vm3 = Number(watcher?.volume_m3);
    if (wkg > 0 && vm3 > 0) return (wkg / vm3).toFixed(2);
    return "—";
  }, [watcher?.weight_kg, watcher?.volume_m3]);

  return (
    <Row gutter={4} align="top" style={{ marginBottom: 4 }}>
      <Form.Item name={[name, "id"]} hidden noStyle><Input /></Form.Item>
      <Col span={5}>
        <Form.Item name={[name, "name"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
          <Input size="small" placeholder={t("order.item_name")} />
        </Form.Item>
      </Col>
      <Col span={2}>
        <Form.Item name={[name, "weight_kg"]} style={{ margin: 0 }}>
          <InputNumber size="small" min={0} precision={3} style={{ width: "100%" }} placeholder="0" />
        </Form.Item>
      </Col>
      <Col span={2}>
        <Form.Item name={[name, "volume_m3"]} style={{ margin: 0 }}>
          <InputNumber size="small" min={0} precision={3} style={{ width: "100%" }} placeholder="0" />
        </Form.Item>
      </Col>
      <Col span={2}>
        <div style={{ paddingTop: 4, fontSize: 12, color: "#666", textAlign: "center" }}>
          {density}
        </div>
      </Col>
      <Col span={3}>
        <Form.Item style={{ margin: 0 }}>
          <Row gutter={2}>
            <Col span={14}>
              <Form.Item name={[name, "price_per_kg"]} style={{ margin: 0 }}>
                <InputNumber size="small" min={0} style={{ width: "100%" }} placeholder="0" />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name={[name, "price_per_kg_currency"]} style={{ margin: 0 }} initialValue="USD">
                <Select size="small" options={CURRENCIES.map(c => ({ value: c, label: c }))} />
              </Form.Item>
            </Col>
          </Row>
        </Form.Item>
      </Col>
      <Col span={3}>
        <Form.Item style={{ margin: 0 }}>
          <Row gutter={2}>
            <Col span={14}>
              <Form.Item name={[name, "cargo_value"]} style={{ margin: 0 }}>
                <InputNumber size="small" min={0} style={{ width: "100%" }} placeholder="0" />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name={[name, "cargo_value_currency"]} style={{ margin: 0 }} initialValue="USD">
                <Select size="small" options={CURRENCIES.map(c => ({ value: c, label: c }))} />
              </Form.Item>
            </Col>
          </Row>
        </Form.Item>
      </Col>
      <Col span={4}>
        <Form.Item name={[name, "supplier_id"]} style={{ margin: 0 }}>
          <Select size="small" allowClear options={supplierOptions} showSearch
            filterOption={(i, o) => String(o?.label ?? "").toLowerCase().includes(i.toLowerCase())}
            placeholder={t("order.item_supplier")} />
        </Form.Item>
      </Col>
      <Col span={2}>
        <Form.Item name={[name, "places_count"]} style={{ margin: 0 }}>
          <InputNumber size="small" min={0} precision={0} style={{ width: "100%" }} placeholder="0" />
        </Form.Item>
      </Col>
      <Col span={1}>
        <Tooltip title={isPurchased ? t("order.item_has_purchase") : undefined}>
          <Button size="small" danger icon={<DeleteOutlined />}
            disabled={isPurchased}
            onClick={() => remove(name)} />
        </Tooltip>
      </Col>
    </Row>
  );
}
