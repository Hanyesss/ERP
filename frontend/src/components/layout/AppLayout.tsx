import { useState } from "react";
import { Layout, Menu, Button, Typography, Space } from "antd";
import { TeamOutlined, DashboardOutlined, ShoppingOutlined, SwapOutlined } from "@ant-design/icons";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { User } from "../../types";
import { logout } from "../../api/auth";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

interface Props {
  user: User;
  onLogout: () => void;
}

export default function AppLayout({ user, onLogout }: Props) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    await logout();
    onLogout();
    navigate("/login");
  };

  const toggleLang = () => {
    const next = i18n.language === "ru" ? "zh" : "ru";
    i18n.changeLanguage(next);
    localStorage.setItem("lang", next);
  };

  const menuItems = [
    { key: "/dashboard", icon: <DashboardOutlined />, label: t("nav.dashboard") },
    { key: "/counterparties", icon: <TeamOutlined />, label: t("nav.counterparties") },
    { key: "/orders", icon: <ShoppingOutlined />, label: t("nav.orders") },
    { key: "/exchange-rates", icon: <SwapOutlined />, label: t("nav.exchange_rates") },
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="light" style={{ borderRight: "1px solid #f0f0f0" }}>
        <div style={{ height: 48, display: "flex", alignItems: "center", justifyContent: "center", borderBottom: "1px solid #f0f0f0", padding: "0 16px" }}>
          {!collapsed && <Text strong style={{ fontSize: 16, whiteSpace: "nowrap" }}>ERP</Text>}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[
            location.pathname.startsWith("/orders") ? "/orders" :
            location.pathname.startsWith("/exchange-rates") ? "/exchange-rates" :
            location.pathname
          ]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ border: "none" }}
        />
      </Sider>

      <Layout>
        <Header style={{ background: "#fff", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #f0f0f0" }}>
          <div style={{ flex: 1 }} />
          <Button type="text" onClick={toggleLang} style={{ fontWeight: 500 }}>
            {t("language.switch")}
          </Button>
          <div style={{ flex: 1 }} />
          <Space>
            <Text>{user.full_name}</Text>
            <Button type="link" onClick={handleLogout} danger>
              {t("nav.logout")}
            </Button>
          </Space>
        </Header>

        <Content style={{ margin: 24, padding: 24, background: "#fff", borderRadius: 8, minHeight: 360 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
