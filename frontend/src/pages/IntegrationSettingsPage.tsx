import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button, Card, Form, Input, Switch, Space, Typography, Alert, Spin, message, Tag, Divider,
} from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from "@ant-design/icons";
import {
  getIntegrationSettings, updateIntegrationSettings, testIntegrationConnection, bulkSyncToSite,
} from "../api/integration";

const { Title, Text } = Typography;

export default function IntegrationSettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [testResult, setTestResult] = useState<{ ok: boolean; message?: string } | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [changingToken, setChangingToken] = useState(false);
  const [bulkResult, setBulkResult] = useState<any | null>(null);

  const bulkSyncMutation = useMutation({
    mutationFn: bulkSyncToSite,
    onSuccess: (r) => {
      setBulkResult(r.data);
      message.success("Синхронизация завершена");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Ошибка синхронизации"),
  });

  const { data: settings, isLoading } = useQuery({
    queryKey: ["integration-settings"],
    queryFn: () => getIntegrationSettings().then(r => r.data),
  });

  const saveMutation = useMutation({
    mutationFn: (values: any) => {
      const payload: any = {
        base_url: values.base_url,
        is_enabled: values.is_enabled,
      };
      if (changingToken && values.api_token) {
        payload.api_token = values.api_token;
      }
      return updateIntegrationSettings(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["integration-settings"] });
      setChangingToken(false);
      message.success(t("common.save") + " ✓");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleTest = async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const values = await form.getFieldsValue();
      const payload: any = {};
      if (values.base_url) payload.base_url = values.base_url;
      if (changingToken && values.api_token) payload.api_token = values.api_token;
      const r = await testIntegrationConnection(payload);
      setTestResult(r.data);
    } catch (e: any) {
      setTestResult({ ok: false, message: e.response?.data?.detail || "Error" });
    } finally {
      setTestLoading(false);
    }
  };

  if (isLoading) return <Spin />;

  return (
    <div style={{ maxWidth: 600 }}>
      <Title level={4} style={{ marginTop: 0, marginBottom: 16 }}>{t("nav.integrations")}</Title>

      <Card>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            base_url: settings?.base_url || "",
            is_enabled: settings?.is_enabled ?? false,
          }}
          onFinish={values => saveMutation.mutate(values)}
        >
          <Form.Item label={t("integration.base_url")} name="base_url">
            <Input placeholder="https://irsway.com" />
          </Form.Item>

          <Form.Item label={t("integration.api_token")}>
            {!changingToken ? (
              <Space>
                <Input.Password
                  value={settings?.api_token_masked || ""}
                  readOnly
                  style={{ width: 300 }}
                />
                <Button onClick={() => setChangingToken(true)}>
                  {t("integration.change_token")}
                </Button>
              </Space>
            ) : (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Form.Item name="api_token" noStyle rules={[{ required: true }]}>
                  <Input.Password placeholder={t("integration.new_token_placeholder")} style={{ width: 360 }} />
                </Form.Item>
                <Button size="small" onClick={() => setChangingToken(false)}>
                  {t("common.cancel")}
                </Button>
              </Space>
            )}
          </Form.Item>

          <Form.Item label={t("integration.enabled")} name="is_enabled" valuePropName="checked">
            <Switch />
          </Form.Item>

          {settings?.last_sync_at && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">
                {t("integration.last_sync")}: {new Date(settings.last_sync_at).toLocaleString("ru-RU")}
                {" — "}
                {settings.last_sync_status === "ok" ? (
                  <Tag color="green">{t("integration.sync_ok")}</Tag>
                ) : (
                  <Tag color="red">{settings.last_sync_status}</Tag>
                )}
              </Text>
              {settings.last_sync_error && (
                <div><Text type="danger" style={{ fontSize: 12 }}>{settings.last_sync_error}</Text></div>
              )}
            </div>
          )}

          {testResult && (
            <Alert
              type={testResult.ok ? "success" : "error"}
              icon={testResult.ok ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
              message={testResult.ok ? t("integration.test_ok") : t("integration.test_fail")}
              description={testResult.message}
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          <Space>
            <Button onClick={handleTest} loading={testLoading}>
              {t("integration.test_connection")}
            </Button>
            <Button type="primary" htmlType="submit" loading={saveMutation.isPending}>
              {t("common.save")}
            </Button>
          </Space>

          <Divider />

          <div>
            <Text strong>Синхронизировать все данные на irsway.com</Text>
            <div style={{ color: "#888", fontSize: 12, marginBottom: 10 }}>
              Торговые заказы, склад, взаиморасчёты — все клиенты сразу
            </div>
            {bulkResult && (
              <Alert
                type={bulkResult.trade_errors + bulkResult.box_errors + bulkResult.recon_errors > 0 ? "warning" : "success"}
                style={{ marginBottom: 10 }}
                message={
                  `Заказы: ${bulkResult.trade_orders} ✓ / ${bulkResult.trade_errors} ✗ · ` +
                  `Коробки: ${bulkResult.boxes} ✓ / ${bulkResult.box_errors} ✗ · ` +
                  `Взаиморасчёты: ${bulkResult.reconciliations} ✓ / ${bulkResult.recon_errors} ✗`
                }
              />
            )}
            <Button
              icon={<SyncOutlined />}
              loading={bulkSyncMutation.isPending}
              onClick={() => { setBulkResult(null); bulkSyncMutation.mutate(); }}
            >
              Синхронизировать всё
            </Button>
          </div>
        </Form>
      </Card>
    </div>
  );
}
