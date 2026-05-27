import { Typography } from "antd";
import { useTranslation } from "react-i18next";
import CounterpartyTable from "../components/counterparties/CounterpartyTable";
import { useHasRole, useHasAnyRole } from "../hooks/useRole";

export default function CounterpartiesPage() {
  const { t } = useTranslation();
  const isManager = useHasRole("manager");
  const isPurchaser = useHasRole("purchaser");
  const canSeeAll = useHasAnyRole("accountant", "admin");

  // Force type filter based on role if they have only one allowed type
  let forcedType: "client" | "supplier" | undefined;
  if (!canSeeAll) {
    if (isManager && !isPurchaser) forcedType = "client";
    else if (isPurchaser && !isManager) forcedType = "supplier";
  }

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 20 }}>
        {t("counterparty.title")}
      </Typography.Title>
      <CounterpartyTable forcedType={forcedType} />
    </div>
  );
}
