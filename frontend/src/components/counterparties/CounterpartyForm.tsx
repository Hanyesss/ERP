import { useEffect } from "react";
import { Modal, Form, Input, Select } from "antd";
import { useTranslation } from "react-i18next";
import type { Counterparty, CounterpartyFormData } from "../../types/counterparty";

interface Props {
  open: boolean;
  editing?: Counterparty | null;
  onClose: () => void;
  onSubmit: (data: CounterpartyFormData) => void;
  loading?: boolean;
}

export default function CounterpartyForm({ open, editing, onClose, onSubmit, loading }: Props) {
  const { t } = useTranslation();
  const [form] = Form.useForm<CounterpartyFormData>();

  useEffect(() => {
    if (open) {
      if (editing) {
        form.setFieldsValue({
          name: editing.name,
          name_cn: editing.name_cn,
          type: editing.type,
          default_currency: editing.default_currency,
          phone: editing.contact_info?.phone,
          email: editing.contact_info?.email,
          address: editing.contact_info?.address,
          notes: editing.notes,
        });
      } else {
        form.resetFields();
        form.setFieldsValue({ default_currency: "CNY" });
      }
    }
  }, [open, editing, form]);

  const handleOk = () => {
    form.validateFields().then(onSubmit);
  };

  const typeOptions = [
    { value: "client", label: t("counterparty.type_client") },
    { value: "supplier", label: t("counterparty.type_supplier") },
    { value: "both", label: t("counterparty.type_both") },
  ];

  const currencyOptions = [
    { value: "CNY", label: "CNY" },
    { value: "RUB", label: "RUB" },
    { value: "USDT", label: "USDT" },
  ];

  return (
    <Modal
      title={editing ? t("counterparty.edit") : t("counterparty.add_new")}
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      okText={t("common.save")}
      cancelText={t("common.cancel")}
      confirmLoading={loading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" size="middle">
        <Form.Item name="name" label={t("counterparty.name")} rules={[{ required: true, message: t("validation.required") }]}>
          <Input />
        </Form.Item>
        <Form.Item name="name_cn" label={t("counterparty.name_cn")}>
          <Input />
        </Form.Item>
        <Form.Item name="type" label={t("counterparty.type")} rules={[{ required: true, message: t("validation.required") }]}>
          <Select options={typeOptions} />
        </Form.Item>
        <Form.Item name="default_currency" label={t("counterparty.default_currency")}>
          <Select options={currencyOptions} />
        </Form.Item>

        <Form.Item label={t("counterparty.contact_info")} style={{ marginBottom: 0 }}>
          <Form.Item name="phone" label={t("counterparty.phone")} style={{ display: "inline-block", width: "calc(50% - 6px)" }}>
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label={t("counterparty.email")}
            style={{ display: "inline-block", width: "calc(50% - 6px)", marginLeft: 12 }}
            rules={[{ type: "email", message: t("validation.invalid_email") }]}
          >
            <Input />
          </Form.Item>
        </Form.Item>
        <Form.Item name="address" label={t("counterparty.address")}>
          <Input />
        </Form.Item>
        <Form.Item name="notes" label={t("counterparty.notes")}>
          <Input.TextArea rows={3} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
