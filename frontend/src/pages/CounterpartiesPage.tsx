import { Typography } from "antd";
import { useTranslation } from "react-i18next";
import CounterpartyTable from "../components/counterparties/CounterpartyTable";

export default function CounterpartiesPage() {
  const { t } = useTranslation();
  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 20 }}>
        {t("counterparty.title")}
      </Typography.Title>
      <CounterpartyTable />
    </div>
  );
}
