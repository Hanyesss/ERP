import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, Button, Card, Typography, Alert } from "antd";
import { useTranslation } from "react-i18next";
import type { User } from "../types";
import { login } from "../api/auth";

const { Title } = Typography;

interface Props {
  onLogin: (user: User) => void;
}

export default function LoginPage({ onLogin }: Props) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: { login: string; password: string }) => {
    setError("");
    setLoading(true);
    try {
      const res = await login(values.login, values.password);
      onLogin(res.data);
      navigate("/dashboard");
    } catch {
      setError(t("login.error"));
    } finally {
      setLoading(false);
    }
  };

  const toggleLang = () => {
    const next = i18n.language === "ru" ? "zh" : "ru";
    i18n.changeLanguage(next);
    localStorage.setItem("lang", next);
  };

  return (
    <div style={{ minHeight: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f2f5", padding: "16px" }}>
      <div style={{ position: "absolute", top: 16, right: 16 }}>
        <Button onClick={toggleLang} type="default">
          {t("language.switch")}
        </Button>
      </div>
      <Card style={{ width: "100%", maxWidth: 380, boxShadow: "0 4px 24px rgba(0,0,0,0.08)" }}>
        <Title level={3} style={{ textAlign: "center", marginBottom: 24 }}>
          {t("login.title")}
        </Title>
        <Typography.Paragraph type="secondary" style={{ textAlign: "center" }}>
          {t("login.welcome")}
        </Typography.Paragraph>
        {error && <Alert message={error} type="error" style={{ marginBottom: 16 }} />}
        <Form onFinish={handleSubmit} layout="vertical" size="large">
          <Form.Item name="login" label={t("login.username")} rules={[{ required: true }]}>
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label={t("login.password")} rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" block loading={loading}>
              {t("login.submit")}
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
