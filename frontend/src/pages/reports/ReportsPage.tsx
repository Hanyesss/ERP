import { Tabs } from "antd";
import { useTranslation } from "react-i18next";
import type { User } from "../../types";
import PnLReport from "./PnLReport";
import ByClientReport from "./ByClientReport";
import BySupplierReport from "./BySupplierReport";
import ExpensesReport from "./ExpensesReport";
import TonnageReport from "./TonnageReport";

interface Props {
  user: User;
}

export default function ReportsPage({ user }: Props) {
  const { t } = useTranslation();

  const isFinance = user.roles?.some(r => ["accountant", "admin"].includes(r));
  const isManager = user.roles?.some(r => r === "manager");

  const items = [
    ...(isFinance ? [
      { key: "pnl", label: t("report.pnl"), children: <PnLReport /> },
      { key: "by_client", label: t("report.by_client"), children: <ByClientReport /> },
      { key: "by_supplier", label: t("report.by_supplier"), children: <BySupplierReport /> },
      { key: "expenses", label: t("report.expenses_structure"), children: <ExpensesReport /> },
    ] : []),
    ...(isFinance || isManager ? [
      { key: "tonnage", label: t("report.tonnage"), children: <TonnageReport /> },
    ] : []),
  ];

  return (
    <div>
      <Tabs items={items} defaultActiveKey={items[0]?.key} />
    </div>
  );
}
