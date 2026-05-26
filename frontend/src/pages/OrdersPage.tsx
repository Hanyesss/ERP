import { Typography } from "antd";
import { useTranslation } from "react-i18next";
import OrderTable from "../components/orders/OrderTable";

const { Title } = Typography;

export default function OrdersPage() {
  const { t } = useTranslation();
  return (
    <div>
      <Title level={4} style={{ marginTop: 0, marginBottom: 16 }}>{t("nav.orders")}</Title>
      <OrderTable />
    </div>
  );
}
