import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button, Card, Form, Input, Switch, Space, Typography, Alert, Spin, message, Tag, Divider, Tabs,
} from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, SyncOutlined, WalletOutlined } from "@ant-design/icons";
import {
  getIntegrationSettings, updateIntegrationSettings, testIntegrationConnection, bulkSyncToSite,
} from "../api/integration";
import {
  getTronTokSettings, updateTronTokSettings, testTronTokConnection, syncTronTokStatus,
} from "../api/trontok";

const { Title, Text } = Typography;

export default function IntegrationSettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const [testResult, setTestResult] = useState<{ ok: boolean; message?: string } | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [changingToken, setChangingToken] = useState(false);
  const [bulkResult, setBulkResult] = useState<any | null>(null);

  const [ttForm] = Form.useForm();
  const [ttChangingKey, setTtChangingKey] = useState(false);
  const [ttTestResult, setTtTestResult] = useState<{ ok: boolean; message?: string } | null>(null);
  const [ttTestLoading, setTtTestLoading] = useState(false);

  const { data: ttSettings, isLoading: ttLoading } = useQuery({
    queryKey: ["trontok-settings"],
    queryFn: () => getTronTokSettings().then(r => r.data),
  });

  const ttSaveMutation = useMutation({
    mutationFn: (values: any) => {
      const payload: any = { is_enabled: values.tt_is_enabled };
      if (values.tt_base_url !== undefined) payload.base_url = values.tt_base_url;
      if (ttChangingKey && values.tt_api_token) payload.api_token = values.tt_api_token;
      return updateTronTokSettings(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trontok-settings"] });
      setTtChangingKey(false);
      message.success("TronTok настройки сохранены");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Ошибка"),
  });

  const handleTtTest = async () => {
    setTtTestLoading(true);
    setTtTestResult(null);
    try {
      const values = ttForm.getFieldsValue();
      const payload: any = {};
      if (ttChangingKey && values.tt_api_token) payload.api_token = values.tt_api_token;
      if (values.tt_base_url) payload.base_url = values.tt_base_url;
      const r = await testTronTokConnection(payload);
      setTtTestResult(r.data);
    } catch (e: any) {
      setTtTestResult({ ok: false, message: e.response?.data?.detail || "Error" });
    } finally {
      setTtTestLoading(false);
    }
  };

  const [syncResult, setSyncResult] = useState<{ checked: number; newly_linked: number; errors: number } | null>(null);
  const syncStatusMutation = useMutation({
    mutationFn: syncTronTokStatus,
    onSuccess: (r) => {
      setSyncResult(r.data);
      qc.invalidateQueries({ queryKey: ["counterparties"] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Ошибка синхронизации"),
  });

  const bulkSyncMutation = useMutation({
    mutationFn: bulkSyncToSite,
    onSuccess: () => {
      setBulkResult({ started: true });
      message.success("Синхронизация запущена в фоне");
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

  const irswayTab = (
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
        {bulkResult?.started && (
          <Alert
            type="info"
            style={{ marginBottom: 10 }}
            message="Синхронизация запущена в фоне — данные обновятся на irsway.com в течение нескольких минут"
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
  );

  const trontokTab = ttLoading ? <Spin /> : (
    <Form
      form={ttForm}
      layout="vertical"
      initialValues={{
        tt_base_url: ttSettings?.base_url || "https://api.trontok.com",
        tt_is_enabled: ttSettings?.is_enabled ?? false,
      }}
      onFinish={values => ttSaveMutation.mutate(values)}
    >
      <div style={{ marginBottom: 16, color: "#888", fontSize: 13 }}>
        Партнёрский ключ хранится только на сервере ERP. Клиент входит напрямую через браузер — ключ никогда не передаётся на irsway.com или в браузер.
      </div>

      <Form.Item label="Base URL" name="tt_base_url">
        <Input placeholder="https://api.trontok.com" style={{ width: 360 }} />
      </Form.Item>

      <Form.Item label="Партнёрский ключ (API key)">
        {!ttChangingKey ? (
          <Space>
            <Input.Password
              value={ttSettings?.api_token_masked || ""}
              readOnly
              style={{ width: 300 }}
            />
            <Button onClick={() => setTtChangingKey(true)}>Изменить ключ</Button>
          </Space>
        ) : (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Form.Item name="tt_api_token" noStyle rules={[{ required: true }]}>
              <Input.Password placeholder="Вставьте партнёрский ключ" style={{ width: 420 }} />
            </Form.Item>
            <Button size="small" onClick={() => setTtChangingKey(false)}>
              {t("common.cancel")}
            </Button>
          </Space>
        )}
      </Form.Item>

      <Form.Item label="Включено" name="tt_is_enabled" valuePropName="checked">
        <Switch />
      </Form.Item>

      {ttTestResult && (
        <Alert
          type={ttTestResult.ok ? "success" : "error"}
          icon={ttTestResult.ok ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
          message={ttTestResult.ok ? "Соединение установлено" : "Ошибка соединения"}
          description={ttTestResult.message}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Space>
        <Button onClick={handleTtTest} loading={ttTestLoading}>
          Проверить соединение
        </Button>
        <Button type="primary" htmlType="submit" loading={ttSaveMutation.isPending}>
          {t("common.save")}
        </Button>
      </Space>

      <Divider />

      <div>
        <Text strong>Синхронизировать статус TronTok у клиентов</Text>
        <div style={{ color: "#888", fontSize: 12, marginBottom: 10 }}>
          Проверяет каждого клиента (по коду) — если кошелёк есть в TronTok, ставит отметку в ERP
        </div>
        {syncResult && (
          <Alert
            type="success"
            style={{ marginBottom: 10 }}
            message={`Проверено: ${syncResult.checked} | Найдено новых: ${syncResult.newly_linked} | Ошибок: ${syncResult.errors}`}
          />
        )}
        <Button
          icon={<SyncOutlined />}
          loading={syncStatusMutation.isPending}
          onClick={() => { setSyncResult(null); syncStatusMutation.mutate(); }}
        >
          Синхронизировать статусы
        </Button>
      </div>
    </Form>
  );

  return (
    <div style={{ maxWidth: 640 }}>
      <Title level={4} style={{ marginTop: 0, marginBottom: 16 }}>{t("nav.integrations")}</Title>

      <Card>
        <Tabs
          defaultActiveKey="irsway"
          items={[
            {
              key: "irsway",
              label: "irsway.com",
              children: irswayTab,
            },
            {
              key: "trontok",
              label: (
                <Space size={4}>
                  <WalletOutlined />
                  TronTok
                  {ttSettings?.is_enabled && <Tag color="green" style={{ marginLeft: 4, fontSize: 11 }}>вкл</Tag>}
                </Space>
              ),
              children: trontokTab,
            },
          ]}
        />
      </Card>
    </div>
  );
}
