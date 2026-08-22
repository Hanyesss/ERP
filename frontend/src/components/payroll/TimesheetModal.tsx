import { useState, useEffect } from "react";
import { Modal, Table, Checkbox, InputNumber, Button, Space, Typography, message } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getAttendance, putAttendance, type AttendanceDay } from "../../api/payroll";

const { Text } = Typography;

interface Props {
  recordId: string | null;
  employeeName: string;
  open: boolean;
  onClose: () => void;
}

const WD = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];

export default function TimesheetModal({ recordId, employeeName, open, onClose }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [days, setDays] = useState<AttendanceDay[]>([]);
  const [year, setYear] = useState(0);
  const [month, setMonth] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["payroll-attendance", recordId],
    queryFn: () => getAttendance(recordId!).then((r) => r.data),
    enabled: open && !!recordId,
  });

  useEffect(() => {
    if (data) {
      setDays(data.days.map((d) => ({ ...d, overtime_hours: Number(d.overtime_hours) })));
      setYear(data.year);
      setMonth(data.month);
    }
  }, [data]);

  const saveMut = useMutation({
    mutationFn: () => putAttendance(recordId!, days),
    onSuccess: () => {
      message.success(t("common.saved"));
      qc.invalidateQueries({ queryKey: ["payroll-month"] });
      qc.invalidateQueries({ queryKey: ["payroll-attendance", recordId] });
      onClose();
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const setDay = (day: number, patch: Partial<AttendanceDay>) =>
    setDays((prev) => prev.map((d) => (d.day === day ? { ...d, ...patch } : d)));

  const markAll = (attended: boolean) =>
    setDays((prev) => prev.map((d) => ({ ...d, attended })));

  const totalDays = days.filter((d) => d.attended).length;
  const totalOt = days.reduce((s, d) => s + (Number(d.overtime_hours) || 0), 0);

  const weekday = (day: number) => {
    if (!year || !month) return "";
    return WD[new Date(year, month - 1, day).getDay()];
  };

  return (
    <Modal
      open={open}
      title={`${t("payroll.timesheet")} · ${employeeName}`}
      onCancel={onClose}
      onOk={() => saveMut.mutate()}
      confirmLoading={saveMut.isPending}
      okText={t("common.save")}
      cancelText={t("common.close")}
      width={520}
    >
      <Space style={{ marginBottom: 8 }} wrap>
        <Button size="small" onClick={() => markAll(true)}>{t("payroll.mark_all_present")}</Button>
        <Button size="small" onClick={() => markAll(false)}>{t("payroll.mark_all_absent")}</Button>
        <Text type="secondary">
          {t("payroll.days_attended")}: <b>{totalDays}</b> · {t("payroll.overtime_hours")}: <b>{totalOt}</b>
        </Text>
      </Space>
      <Table
        size="small"
        loading={isLoading}
        pagination={false}
        scroll={{ y: 420 }}
        dataSource={days}
        rowKey="day"
        columns={[
          {
            title: t("payroll.day"),
            dataIndex: "day",
            width: 80,
            render: (d: number) => {
              const wd = weekday(d);
              const weekend = wd === "сб" || wd === "вс";
              return <span style={{ color: weekend ? "#cf1322" : undefined }}>{d} <Text type="secondary">{wd}</Text></span>;
            },
          },
          {
            title: t("payroll.present"),
            dataIndex: "attended",
            width: 90,
            align: "center",
            render: (v: boolean, r: AttendanceDay) => (
              <Checkbox checked={v} onChange={(e) => setDay(r.day, { attended: e.target.checked })} />
            ),
          },
          {
            title: t("payroll.overtime_h"),
            dataIndex: "overtime_hours",
            render: (v: number, r: AttendanceDay) => (
              <InputNumber
                min={0}
                max={24}
                step={0.5}
                value={Number(v)}
                onChange={(val) => setDay(r.day, { overtime_hours: Number(val) || 0 })}
                style={{ width: 100 }}
              />
            ),
          },
        ]}
      />
    </Modal>
  );
}
