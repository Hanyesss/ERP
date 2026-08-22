import { useState } from "react";
import { Layout, Menu, Button, Typography, Space, Tooltip, Drawer, Badge } from "antd";
import { useQuery } from "@tanstack/react-query";
import {
  TeamOutlined, DashboardOutlined, ShoppingOutlined,
  SwapOutlined, ShoppingCartOutlined, WalletOutlined, AccountBookOutlined,
  BarChartOutlined, DatabaseOutlined, SettingOutlined, BankOutlined,
  MenuOutlined, CloseOutlined, SafetyCertificateOutlined, GiftOutlined,
  DiffOutlined, SolutionOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { User, UserRole } from "../../types";
import { logout } from "../../api/auth";
import { getQuotesPendingCount } from "../../api/logisticsQuotes";
import NotificationBell from "../notifications/NotificationBell";
import { useIsMobile } from "../../hooks/useIsMobile";
import { useNavigationGuard } from "../../contexts/NavigationGuardContext";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

interface Props {
  user: User;
  onLogout: () => void;
}

function hasRole(user: User, ...roles: UserRole[]): boolean {
  return roles.some((r) => user.roles?.includes(r));
}

export default function AppLayout({ user, onLogout }: Props) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobile();
  const canSeeQuotes = hasRole(user, "employee", "admin");
  const { data: quotesPending } = useQuery({
    queryKey: ["quotes-pending-count"],
    queryFn: () => getQuotesPendingCount().then(r => r.data.count),
    enabled: canSeeQuotes,
    refetchInterval: 60000,
  });
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { checkGuard } = useNavigationGuard();

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
    hasRole(user, "partner") && {
      key: "/partner-dashboard",
      icon: <GiftOutlined />,
      label: t("nav.partner_dashboard"),
    },

    !hasRole(user, "partner") && { key: "/dashboard", icon: <DashboardOutlined />, label: t("nav.dashboard") },

    !hasRole(user, "partner") && {
      key: "/counterparties",
      icon: <TeamOutlined />,
      label: t("nav.counterparties"),
    },

    hasRole(user, "employee", "seller", "manager", "purchaser", "accountant", "admin") && {
      key: "/orders",
      icon: <ShoppingOutlined />,
      label: t("nav.orders"),
    },

    hasRole(user, "purchaser", "manager", "accountant", "admin") && {
      key: "/purchases",
      icon: <ShoppingCartOutlined />,
      label: t("nav.purchases"),
    },

    hasRole(user, "employee", "admin") && {
      key: "/quotes",
      icon: <DiffOutlined />,
      label: (
        <Space size={6}>
          {t("nav.quotes")}
          {!!quotesPending && <Badge count={quotesPending} size="small" />}
        </Space>
      ),
    },

    !hasRole(user, "partner") && {
      key: "/payments",
      icon: <WalletOutlined />,
      label: t("nav.payments"),
    },

    hasRole(user, "accountant", "admin") && {
      key: "/cash-registers",
      icon: <BankOutlined />,
      label: t("nav.cash_registers"),
    },

    !hasRole(user, "partner") && {
      key: "/expenses",
      icon: <AccountBookOutlined />,
      label: t("nav.expenses"),
    },

    hasRole(user, "accountant", "admin") && {
      key: "/exchange-rates",
      icon: <SwapOutlined />,
      label: t("nav.exchange_rates"),
    },

    hasRole(user, "accountant", "admin") && {
      key: "/payroll",
      icon: <SolutionOutlined />,
      label: t("nav.payroll"),
    },

    hasRole(user, "employee", "seller", "accountant", "admin") && {
      key: "/warehouses",
      icon: <DatabaseOutlined />,
      label: t("nav.warehouses"),
    },

    hasRole(user, "seller", "accountant", "admin") && {
      key: "/reports",
      icon: <BarChartOutlined />,
      label: t("nav.reports"),
    },

    hasRole(user, "admin", "manager") && {
      key: "/assets",
      icon: <SafetyCertificateOutlined />,
      label: t("nav.assets"),
    },

    hasRole(user, "accountant", "admin") && {
      key: "/admin-partners",
      icon: <GiftOutlined />,
      label: t("nav.admin_partners"),
    },

    hasRole(user, "admin") && {
      key: "/users",
      icon: <TeamOutlined />,
      label: t("nav.users"),
    },

    hasRole(user, "admin") && {
      key: "/settings/integrations",
      icon: <SettingOutlined />,
      label: t("nav.integrations"),
    },
  ].filter(Boolean) as { key: string; icon: JSX.Element; label: string }[];

  const selectedKey = location.pathname.startsWith("/orders")
    ? "/orders"
    : location.pathname.startsWith("/purchases")
    ? "/purchases"
    : location.pathname.startsWith("/payments")
    ? "/payments"
    : location.pathname.startsWith("/expenses")
    ? "/expenses"
    : location.pathname.startsWith("/exchange-rates")
    ? "/exchange-rates"
    : location.pathname.startsWith("/payroll")
    ? "/payroll"
    : location.pathname.startsWith("/cash-registers")
    ? "/cash-registers"
    : location.pathname.startsWith("/warehouses")
    ? "/warehouses"
    : location.pathname.startsWith("/reports")
    ? "/reports"
    : location.pathname.startsWith("/assets")
    ? "/assets"
    : location.pathname.startsWith("/partner-dashboard")
    ? "/partner-dashboard"
    : location.pathname.startsWith("/admin-partners")
    ? "/admin-partners"
    : location.pathname.startsWith("/users")
    ? "/users"
    : location.pathname.startsWith("/settings/integrations")
    ? "/settings/integrations"
    : location.pathname;

  const handleMenuClick = ({ key }: { key: string }) => {
    checkGuard().then(canNav => {
      if (!canNav) return;
      navigate(key);
      if (isMobile) setDrawerOpen(false);
    });
  };

  const menuContent = (
    <>
      <div style={{
        height: 48,
        display: "flex",
        alignItems: "center",
        justifyContent: isMobile ? "space-between" : "center",
        borderBottom: "1px solid #f0f0f0",
        padding: "0 16px",
        flexShrink: 0,
      }}>
        <Text strong style={{ fontSize: 16, whiteSpace: "nowrap" }}>IRS ERP</Text>
        {isMobile && (
          <Button type="text" icon={<CloseOutlined />} onClick={() => setDrawerOpen(false)} />
        )}
      </div>
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{ border: "none", flex: 1, overflowY: "auto" }}
      />
      {!isMobile && !collapsed && (
        <div style={{ textAlign: "center", padding: "8px 0 48px" }}>
          <Tooltip title="Разработал Hanyesss">
            <Text type="secondary" style={{ fontSize: 11 }}>by Hanyesss</Text>
          </Tooltip>
        </div>
      )}
    </>
  );

  return (
    <Layout style={{ minHeight: "100dvh" }}>
      {/* Desktop sidebar */}
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme="light"
          style={{ borderRight: "1px solid #f0f0f0" }}
        >
          {menuContent}
        </Sider>
      )}

      {/* Mobile drawer */}
      {isMobile && (
        <Drawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          placement="left"
          width={220}
          styles={{ body: { padding: 0, display: "flex", flexDirection: "column" }, header: { display: "none" } }}
          style={{ top: 0 }}
        >
          {menuContent}
        </Drawer>
      )}

      <Layout>
        <Header style={{
          background: "#fff",
          padding: isMobile ? "0 12px" : "0 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #f0f0f0",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}>
          <Space>
            {isMobile && (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setDrawerOpen(true)}
                style={{ fontSize: 18 }}
              />
            )}
            {isMobile && <Text strong style={{ fontSize: 15 }}>IRS ERP</Text>}
          </Space>

          <Space size={isMobile ? 4 : 12}>
            <Button type="text" onClick={toggleLang} style={{ fontWeight: 500, fontSize: isMobile ? 12 : 14 }}>
              {t("language.switch")}
            </Button>
            <NotificationBell />
            {!isMobile && <Text style={{ fontSize: 13 }}>{user.full_name}</Text>}
            <Button type="link" onClick={handleLogout} danger style={{ padding: isMobile ? "0 4px" : undefined, fontSize: isMobile ? 12 : 14 }}>
              {t("nav.logout")}
            </Button>
          </Space>
        </Header>

        <Content style={{
          margin: isMobile ? 8 : 24,
          padding: isMobile ? 12 : 24,
          background: "#fff",
          borderRadius: 8,
          minHeight: 360,
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
