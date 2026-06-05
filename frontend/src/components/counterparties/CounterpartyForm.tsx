import { useEffect, useState } from "react";
import { Modal, Form, Input, Select, Checkbox, Divider } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { Counterparty, CounterpartyFormData } from "../../types/counterparty";
import { getCounterparties } from "../../api/counterparties";

export interface CounterpartyFormValues extends CounterpartyFormData {
  create_site_account?: boolean;
  site_login?: string;
  site_password?: string;
  // при редактировании
  current_site_login?: string;
  new_site_login?: string;
  new_site_password?: string;
}

interface Props {
  open: boolean;
  editing?: Counterparty | null;
  onClose: () => void;
  onSubmit: (data: CounterpartyFormValues) => void;
  loading?: boolean;
  forcedType?: "client" | "supplier";
}

export default function CounterpartyForm({ open, editing, onClose, onSubmit, loading, forcedType }: Props) {
  const { t } = useTranslation();
  const [form] = Form.useForm<CounterpartyFormValues>();
  const [createAccount, setCreateAccount] = useState(false);
  const [changeCredentials, setChangeCredentials] = useState(false);

  const watchedType = Form.useWatch("type", form);
  const isClient = watchedType === "client" || watchedType === "both";
  const isPartner = watchedType === "partner";

  // Partners list for the client → partner link dropdown
  const { data: partnersData } = useQuery({
    queryKey: ["counterparties", "partners-list"],
    queryFn: () => getCounterparties({ type: "partner", page_size: 500 }).then((r) => r.data),
    enabled: open,
  });
  const partnerOptions = (partnersData?.items ?? []).map((p) => ({ value: p.id, label: p.name }));

  useEffect(() => {
    if (open) {
      setCreateAccount(false);
      setChangeCredentials(false);
      if (editing) {
        form.setFieldsValue({
          name: editing.name,
          name_cn: editing.name_cn,
          code: editing.code,
          type: editing.type,
          default_currency: editing.default_currency,
          phone: editing.contact_info?.phone,
          email: editing.contact_info?.email,
          address: editing.contact_info?.address,
          notes: editing.notes,
          partner_id: editing.partner_id,
        });
      } else {
        form.resetFields();
        form.setFieldsValue({ default_currency: "CNY", type: forcedType });
      }
    }
  }, [open, editing, form]);

  const handleOk = () => {
    form.validateFields().then((values) => {
      onSubmit({
        ...values,
        create_site_account: createAccount,
      });
    });
  };

  const typeOptions = [
    { value: "client", label: t("counterparty.type_client") },
    { value: "supplier", label: t("counterparty.type_supplier") },
    { value: "both", label: t("counterparty.type_both") },
    { value: "partner", label: t("counterparty.type_partner") },
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
        <Form.Item
          name="code"
          label={t("counterparty.code")}
          tooltip={t("counterparty.code_hint")}
          rules={isClient ? [{ required: true, message: t("validation.required") }] : []}
        >
          <Input maxLength={20} style={{ width: 160 }} placeholder="A2424" />
        </Form.Item>
        <Form.Item name="type" label={t("counterparty.type")} rules={[{ required: true, message: t("validation.required") }]}>
          <Select options={forcedType ? typeOptions.filter(o => o.value === forcedType) : typeOptions} disabled={!!forcedType && !editing} />
        </Form.Item>
        <Form.Item name="default_currency" label={t("counterparty.default_currency")}>
          <Select options={currencyOptions} />
        </Form.Item>

        {isClient && (
          <Form.Item name="partner_id" label={t("counterparty.partner")}>
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder={t("counterparty.partner_select")}
              options={partnerOptions}
            />
          </Form.Item>
        )}

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

        {!editing && (isClient || isPartner) && (
          <>
            <Divider style={{ margin: "12px 0" }} />
            <Checkbox
              checked={createAccount}
              onChange={(e) => setCreateAccount(e.target.checked)}
            >
              {t("counterparty.create_site_account")}
            </Checkbox>
            {createAccount && (
              <div style={{ marginTop: 12 }}>
                <Form.Item
                  name="site_login"
                  label={t("counterparty.site_login")}
                  rules={[{ required: createAccount, message: t("validation.required") }]}
                >
                  <Input autoComplete="new-password" />
                </Form.Item>
                <Form.Item
                  name="site_password"
                  label={t("counterparty.site_password")}
                  rules={[{ required: createAccount, message: t("validation.required") }, { min: 8, message: t("validation.min_length", { min: 8 }) }]}
                >
                  <Input.Password autoComplete="new-password" />
                </Form.Item>
              </div>
            )}
          </>
        )}

        {editing && isClient && (
          <>
            <Divider style={{ margin: "12px 0" }} />
            <Checkbox
              checked={changeCredentials}
              onChange={(e) => setChangeCredentials(e.target.checked)}
            >
              {t("counterparty.change_site_credentials")}
            </Checkbox>
            {changeCredentials && (
              <div style={{ marginTop: 12 }}>
                <Form.Item
                  name="current_site_login"
                  label={t("counterparty.current_site_login")}
                  rules={[{ required: changeCredentials, message: t("validation.required") }]}
                >
                  <Input autoComplete="off" />
                </Form.Item>
                <Form.Item name="new_site_login" label={t("counterparty.new_site_login")}>
                  <Input autoComplete="off" />
                </Form.Item>
                <Form.Item
                  name="new_site_password"
                  label={t("counterparty.new_site_password")}
                  rules={[
                    { min: 8, message: t("validation.min_length", { min: 8 }) },
                  ]}
                >
                  <Input.Password autoComplete="new-password" />
                </Form.Item>
              </div>
            )}
          </>
        )}
      </Form>
    </Modal>
  );
}
