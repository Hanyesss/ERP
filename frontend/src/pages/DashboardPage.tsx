import { Typography } from "antd";
import { useTranslation } from "react-i18next";
import type { User } from "../types";

interface Props {
  user: User;
}

export default function DashboardPage({ user }: Props) {
  const { t } = useTranslation();
  return (
    <Typography.Title level={4} style={{ marginTop: 0 }}>
      {t("dashboard.welcome")}, {user.full_name}
    </Typography.Title>
  );
}
