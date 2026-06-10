import { useState } from "react";
import { Form, Input, InputNumber, Select, Button, Row, Col, Typography, Popover, Tooltip } from "antd";
import { DeleteOutlined, PlusOutlined, FileTextOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import type { FormInstance } from "antd";
import CounterpartySelect from "../common/CounterpartySelect";
import ItemPhotosPicker, { type LocalPhoto } from "./ItemPhotosPicker";
import ItemPhotosEditor from "./ItemPhotosEditor";

const { Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

export interface PendingItemPhotos {
  [fieldKey: number]: LocalPhoto[];
}

interface Props {
  form: FormInstance;
  rates: Record<string, number>;
  clientCurrency: string;
  pendingPhotos: PendingItemPhotos;
  onPendingPhotosChange: (photos: PendingItemPhotos) => void;
  /** Maps Form.List field key → saved item ID (for edit mode) */
  savedItemIdByKey?: Record<number, string>;
  /** Set of item IDs that have linked purchases and cannot be deleted */
  purchasedItemIds?: Set<string>;
}

function SpecPopover({ value, onChange }: { value?: string; onChange?: (v: string) => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      trigger="click"
      placement="right"
      content={
        <div style={{ width: 300 }}>
          <Input.TextArea
            rows={6}
            value={value}
            onChange={e => onChange?.(e.target.value)}
            placeholder={t("order.specification")}
            autoFocus
          />
        </div>
      }
      title={t("order.specification")}
    >
      <Button
        size="small"
        icon={<FileTextOutlined />}
        type={value ? "primary" : "default"}
        ghost={!!value}
        style={{ width: "100%" }}
        title={value || t("order.spec_add")}
      >
        {value ? "✓" : "…"}
      </Button>
    </Popover>
  );
}

export default function OrderItemsEditor({
  form, rates, clientCurrency,
  pendingPhotos, onPendingPhotosChange,
  savedItemIdByKey = {},
  purchasedItemIds,
}: Props) {
  const { t } = useTranslation();

  return (
    <Form.List name="items">
      {(fields, { add, remove }) => (
        <div>
          <Row gutter={4} style={{ marginBottom: 4, paddingLeft: 4 }}>
            {[
              [t("order.item_name"), 3],
              ["CN", 3],
              [t("order.model"), 2],
              [t("order.specification"), 2],
              [t("order.item_quantity"), 2],
              [t("order.item_unit"), 1],
              [t("order.item_sale_price"), 2],
              ["Вал.", 2],
              [t("order.item_preferred_supplier"), 3],
              [t("order.photos"), 3],
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
              <Row key={key} gutter={4} align="top" style={{ marginBottom: 8 }}>
                <Form.Item name={[name, "id"]} hidden noStyle><Input /></Form.Item>
                <Col span={3}>
                  <Form.Item name={[name, "name"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
                    <Input size="small" placeholder={t("order.item_name")} />
                  </Form.Item>
                </Col>
                <Col span={3}>
                  <Form.Item name={[name, "name_cn"]} style={{ margin: 0 }}>
                    <Input size="small" placeholder="中文名" />
                  </Form.Item>
                </Col>
                <Col span={2}>
                  <Form.Item name={[name, "model"]} style={{ margin: 0 }}>
                    <Input size="small" placeholder={t("order.model")} />
                  </Form.Item>
                </Col>
                <Col span={2}>
                  <Form.Item name={[name, "specification"]} style={{ margin: 0 }}>
                    <SpecPopover />
                  </Form.Item>
                </Col>
                <Col span={2}>
                  <Form.Item name={[name, "quantity"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
                    <InputNumber size="small" min={0} style={{ width: "100%" }} placeholder="0" />
                  </Form.Item>
                </Col>
                <Col span={1}>
                  <Form.Item name={[name, "unit"]} style={{ margin: 0 }}>
                    <Input size="small" placeholder="шт" />
                  </Form.Item>
                </Col>
                <Col span={2}>
                  <Form.Item name={[name, "sale_price"]} rules={[{ required: true, message: "" }]} style={{ margin: 0 }}>
                    <InputNumber size="small" min={0} style={{ width: "100%" }} placeholder="0" />
                  </Form.Item>
                </Col>
                <Col span={2}>
                  <Form.Item name={[name, "sale_currency"]} style={{ margin: 0 }} initialValue={clientCurrency || "CNY"}>
                    <Select size="small" options={CURRENCIES.map(c => ({ value: c, label: c }))} />
                  </Form.Item>
                </Col>
                <Col span={3}>
                  <Form.Item name={[name, "preferred_supplier_id"]} style={{ margin: 0 }}>
                    <CounterpartySelect
                      type="supplier" size="small" allowClear
                      placeholder={t("order.item_preferred_supplier_hint")}
                      style={{ fontSize: 12 }}
                    />
                  </Form.Item>
                </Col>
                <Col span={3}>
                  {savedItemId ? (
                    /* Existing item: show real photos from API, upload/delete immediately */
                    <ItemPhotosEditor itemId={savedItemId} />
                  ) : (
                    /* New item: queue photos locally, upload after order is saved */
                    <ItemPhotosPicker
                      photos={pendingPhotos[key] || []}
                      onChange={photos => onPendingPhotosChange({ ...pendingPhotos, [key]: photos })}
                    />
                  )}
                </Col>
                <Col span={1}>
                  <Tooltip title={isPurchased ? t("order.item_has_purchase") : undefined}>
                    <Button
                      size="small" danger icon={<DeleteOutlined />}
                      disabled={isPurchased}
                      onClick={() => {
                        remove(name);
                        const updated = { ...pendingPhotos };
                        delete updated[key];
                        onPendingPhotosChange(updated);
                      }}
                    />
                  </Tooltip>
                </Col>
              </Row>
            );
          })}

          <Button
            type="dashed" icon={<PlusOutlined />}
            onClick={() => add({ sale_currency: clientCurrency || "CNY" })}
            style={{ width: "100%", marginTop: 8 }}
          >
            {t("order.add_item")}
          </Button>
        </div>
      )}
    </Form.List>
  );
}
