import { useNavigate } from "react-router-dom";
import { Button, Typography, Space } from "antd";
import { useTranslation } from "react-i18next";
import type { User } from "../types";
import { logout } from "../api/auth";

const { Title } = Typography;

interface Props {
  user: User;
  onLogout: () => void;
}

export default function DashboardPage({ user, onLogout }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    onLogout();
    navigate("/login");
  };

  return (
    <div style={{ padding: 48 }}>
      <Space direction="vertical" size="large">
        <Title level={2}>
          {t("dashboard.welcome")}, {user.full_name}
        </Title>
        <Button danger onClick={handleLogout}>
          {t("dashboard.logout")}
        </Button>
      </Space>
    </div>
  );
}
