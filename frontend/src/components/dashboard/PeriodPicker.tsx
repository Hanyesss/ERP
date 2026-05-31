import { useState } from "react";
import { Button, DatePicker, Space } from "antd";
import { useTranslation } from "react-i18next";
import dayjs, { Dayjs } from "dayjs";
import quarterOfYear from "dayjs/plugin/quarterOfYear";

dayjs.extend(quarterOfYear);

export interface Period {
  date_from: string;
  date_to: string;
}

const { RangePicker } = DatePicker;

interface Props {
  value: Period;
  onChange: (p: Period) => void;
}

export default function PeriodPicker({ value, onChange }: Props) {
  const { t } = useTranslation();
  // Track which preset was clicked — prevents two buttons being active simultaneously
  const [activeKey, setActiveKey] = useState<string>("month");

  const set = (key: string, from: Dayjs, to: Dayjs) => {
    setActiveKey(key);
    onChange({ date_from: from.format("YYYY-MM-DD"), date_to: to.format("YYYY-MM-DD") });
  };

  const presets = [
    { key: "today",   label: t("dashboard.period_today"),   from: dayjs(),                          to: dayjs() },
    { key: "week",    label: t("dashboard.period_week"),    from: dayjs().subtract(6, "day"),        to: dayjs() },
    { key: "month",   label: t("dashboard.period_month"),   from: dayjs().startOf("month"),          to: dayjs() },
    { key: "quarter", label: t("dashboard.period_quarter"), from: dayjs().startOf("quarter"),        to: dayjs().endOf("quarter") },
    { key: "year",    label: t("dashboard.period_year"),    from: dayjs().startOf("year"),           to: dayjs().endOf("year") },
  ];

  return (
    <Space wrap size={4}>
      {presets.map(p => (
        <Button
          key={p.key}
          size="small"
          type={activeKey === p.key ? "primary" : "default"}
          onClick={() => set(p.key, p.from, p.to)}
        >
          {p.label}
        </Button>
      ))}
      <RangePicker
        size="small"
        value={[dayjs(value.date_from), dayjs(value.date_to)]}
        onChange={range => {
          if (range?.[0] && range?.[1]) {
            setActiveKey("custom");
            onChange({
              date_from: range[0].format("YYYY-MM-DD"),
              date_to: range[1].format("YYYY-MM-DD"),
            });
          }
        }}
        allowClear={false}
      />
    </Space>
  );
}
