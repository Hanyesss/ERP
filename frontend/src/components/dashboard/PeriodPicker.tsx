import { Button, DatePicker, Space } from "antd";
import { useTranslation } from "react-i18next";
import dayjs, { Dayjs } from "dayjs";

export interface Period {
  date_from: string;
  date_to: string;
}

const { RangePicker } = DatePicker;

const today = () => dayjs();
const startOfMonth = () => today().startOf("month");
const startOfWeek = () => today().startOf("week");
const startOfQuarter = () => today().startOf("quarter" as any);
const startOfYear = () => today().startOf("year");

interface Props {
  value: Period;
  onChange: (p: Period) => void;
}

export default function PeriodPicker({ value, onChange }: Props) {
  const { t } = useTranslation();
  const set = (from: Dayjs, to: Dayjs) =>
    onChange({ date_from: from.format("YYYY-MM-DD"), date_to: to.format("YYYY-MM-DD") });

  const isActive = (from: Dayjs, to: Dayjs) =>
    value.date_from === from.format("YYYY-MM-DD") && value.date_to === to.format("YYYY-MM-DD");

  const presets = [
    { label: t("dashboard.period_today"), from: today(), to: today() },
    { label: t("dashboard.period_week"), from: startOfWeek(), to: today() },
    { label: t("dashboard.period_month"), from: startOfMonth(), to: today() },
    { label: t("dashboard.period_quarter"), from: startOfQuarter(), to: today() },
    { label: t("dashboard.period_year"), from: startOfYear(), to: today() },
  ];

  return (
    <Space wrap size={4}>
      {presets.map(p => (
        <Button
          key={p.label}
          size="small"
          type={isActive(p.from, p.to) ? "primary" : "default"}
          onClick={() => set(p.from, p.to)}
        >
          {p.label}
        </Button>
      ))}
      <RangePicker
        size="small"
        value={[dayjs(value.date_from), dayjs(value.date_to)]}
        onChange={range => {
          if (range?.[0] && range?.[1]) set(range[0], range[1]);
        }}
        allowClear={false}
      />
    </Space>
  );
}
