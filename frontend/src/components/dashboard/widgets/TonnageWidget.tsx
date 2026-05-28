import { Card } from "antd";
import { useTranslation } from "react-i18next";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function TonnageWidget({ data }: { data: any[] }) {
  const { t } = useTranslation();
  return (
    <Card title={t("dashboard.tonnage")} size="small">
      {data.length === 0 ? (
        <div style={{ color: "#999", textAlign: "center", padding: 24 }}>{t("dashboard.no_data")}</div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={v => v.toLocaleString("ru-RU")} />
            <YAxis type="category" dataKey="warehouse" tick={{ fontSize: 11 }} width={100} />
            <Tooltip formatter={(v: any) => (v as number).toLocaleString("ru-RU") + " кг"} />
            <Bar dataKey="kg" fill="#1890ff" name="кг" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
