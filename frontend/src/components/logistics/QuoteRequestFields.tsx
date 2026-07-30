import { Form, Input, InputNumber, Select, Space } from "antd";
import { useTranslation } from "react-i18next";

// Предустановленные виды упаковки (значение = подпись на текущем языке; можно вводить своё)
export function usePackagingOptions() {
  const { t } = useTranslation();
  return ["carton", "pallet", "crate", "frame", "wrap"].map(k => {
    const label = t(`quote.pack_${k}`);
    return { value: label, label };
  });
}

/** Ручные поля заявки — используются в форме создания и редактирования. */
export default function QuoteRequestFields() {
  const { t } = useTranslation();
  const packaging = usePackagingOptions();

  return (
    <>
      <Form.Item name="order_number" label={t("quote.order_number")}>
        <Input />
      </Form.Item>
      <Form.Item name="product_name" label={t("quote.product")}>
        <Input />
      </Form.Item>
      <Form.Item name="box" label={t("quote.box")} tooltip={t("quote.box_hint")}>
        <Select
          mode="tags"
          allowClear
          options={packaging}
          placeholder={t("quote.box_placeholder")}
          tokenSeparators={[","]}
        />
      </Form.Item>
      <Space wrap>
        <Form.Item name="dimensions" label={t("quote.dimensions")}>
          <Input style={{ width: 150 }} placeholder="51*46*35" />
        </Form.Item>
        <Form.Item name="cargo_value" label={t("quote.cargo_value")}>
          <Input style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="client_price" label={t("quote.client_price")}>
          <InputNumber min={0} step={0.1} style={{ width: 140 }} />
        </Form.Item>
      </Space>
      <Space wrap>
        <Form.Item name="weight_kg" label={t("quote.weight")}>
          <InputNumber min={0} step={0.1} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="volume_m3" label={t("quote.volume")}>
          <InputNumber min={0} step={0.01} style={{ width: 120 }} />
        </Form.Item>
      </Space>
      <Space wrap>
        <Form.Item name="destination" label={t("quote.destination")}>
          <Input style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="dispatch_place" label={t("quote.dispatch")}>
          <Input style={{ width: 160 }} />
        </Form.Item>
      </Space>
    </>
  );
}
