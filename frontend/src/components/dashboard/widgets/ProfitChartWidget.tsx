import { Card, Empty } from "antd";
import { useTranslation } from "react-i18next";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { Period } from "../PeriodPicker";

interface Props {
  data: any[];
  period?: Period;
}

export default function ProfitChartWidget({ data, period }: Props) {
  const { t } = useTranslation();

  const chartData = (data || []).map(d => ({
    ...d,
    month: String(d.month).slice(0, 7),
  }));

  // Subtitle: show period range
  const subtitle = period
    ? `${period.date_from} — ${period.date_to}`
    : undefined;

  return (
    <Card
      title={t("dashboard.profit_dynamics")}
      extra={subtitle && <span style={{ fontSize: 12, color: "#888" }}>{subtitle}</span>}
      size="small"
    >
      {chartData.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t("common.no_data") || "Нет данных за период"}
          style={{ padding: "24px 0" }}
        />
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={v => (v / 1000).toFixed(0) + "K"}
            />
            <Tooltip
              formatter={(v: any) =>
                (v as number).toLocaleString("ru-RU", { maximumFractionDigits: 0 }) + " CNY"
              }
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="#1890ff"
              name={t("dashboard.revenue")}
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="profit"
              stroke="#52c41a"
              name={t("dashboard.net_profit")}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
