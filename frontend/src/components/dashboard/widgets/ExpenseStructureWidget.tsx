import { Card } from "antd";
import { useTranslation } from "react-i18next";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

const COLORS = ["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2", "#eb2f96"];

export default function ExpenseStructureWidget({ data }: { data: any[] }) {
  const { t } = useTranslation();
  return (
    <Card title={t("dashboard.expense_structure")} size="small">
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="category"
            cx="50%"
            cy="50%"
            outerRadius={80}
            label={({ category, percent }: any) => `${category} ${((percent || 0) * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v: any) => (v as number).toLocaleString("ru-RU", { maximumFractionDigits: 0 }) + " CNY"} />
        </PieChart>
      </ResponsiveContainer>
    </Card>
  );
}
