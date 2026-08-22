import { useState } from "react";
import {
  Card, Table, Button, DatePicker, InputNumber, Space, Typography, Tag,
  Modal, Form, Input, Select, message,
} from "antd";
import { PlusOutlined, TableOutlined, DollarOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import {
  getMonth, patchRecord, createEmployee, payRecord, availableUsers, type PayrollRow,
} from "../api/payroll";
import { getCashRegisters } from "../api/cashRegisters";
import TimesheetModal from "../components/payroll/TimesheetModal";
import type { ColumnsType } from "antd/es/table";

const { Title, Text } = Typography;

const fmt = (v: number | string | null | undefined) =>
  Number(v ?? 0).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Число с сохранением по blur (если изменилось). */
function EditableNum({ value, disabled, onSave, style }: {
  value: number; disabled?: boolean; onSave: (v: number) => void; style?: React.CSSProperties;
}) {
  const [val, setVal] = useState<number>(Number(value));
  return (
    <InputNumber
      value={val}
      disabled={disabled}
      min={0}
      step={1}
      controls={false}
      style={{ width: 110, ...style }}
      onChange={(v) => setVal(Number(v) || 0)}
      onBlur={() => { if (Number(val) !== Number(value)) onSave(Number(val)); }}
    />
  );
}

export default function PayrollPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [month, setMonth] = useState(dayjs());
  const [timesheet, setTimesheet] = useState<{ id: string; name: string } | null>(null);
  const [payTarget, setPayTarget] = useState<PayrollRow | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [addForm] = Form.useForm();
  const [payForm] = Form.useForm();

  const year = month.year();
  const mon = month.month() + 1;

  const { data, isLoading } = useQuery({
    queryKey: ["payroll-month", year, mon],
    queryFn: () => getMonth(year, mon).then((r) => r.data),
  });

  const { data: registers = [] } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then((r) => r.data),
  });

  const { data: freeUsers = [] } = useQuery({
    queryKey: ["payroll-available-users"],
    queryFn: () => availableUsers().then((r) => r.data),
    enabled: addOpen,
  });

  const patchMut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: any }) => patchRecord(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll-month", year, mon] }),
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const addMut = useMutation({
    mutationFn: (v: any) => createEmployee(v),
    onSuccess: () => {
      message.success(t("common.saved"));
      setAddOpen(false);
      addForm.resetFields();
      qc.invalidateQueries({ queryKey: ["payroll-month", year, mon] });
      qc.invalidateQueries({ queryKey: ["payroll-available-users"] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const payMut = useMutation({
    mutationFn: (v: any) => payRecord(payTarget!.id, v),
    onSuccess: () => {
      message.success(t("payroll.paid_ok"));
      setPayTarget(null);
      payForm.resetFields();
      qc.invalidateQueries({ queryKey: ["payroll-month", year, mon] });
      qc.invalidateQueries({ queryKey: ["cash-registers"] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const save = (id: string, field: string, v: number) =>
    patchMut.mutate({ id, patch: { [field]: v } });

  const rows = data?.rows ?? [];

  const payRegId = Form.useWatch("cash_register_id", payForm);
  const payReg = (registers as any[]).find((r) => r.id === payRegId);
  const payRegCur: string = payReg?.currency ?? "CNY";
  const needCashRate = !!payReg && payRegCur !== "CNY";

  const columns: ColumnsType<PayrollRow> = [
    {
      title: t("payroll.employee"), dataIndex: "employee_name", key: "emp", fixed: "left", width: 150,
      render: (v, r) => (
        <div>
          <div>{v} {r.is_paid && <Tag color="green">{t("payroll.paid")}</Tag>}</div>
          {(r.role || r.position) && (
            <Text type="secondary" style={{ fontSize: 12 }}>{r.role ? t(`role.${r.role}`) : r.position}</Text>
          )}
        </div>
      ),
    },
    {
      title: t("payroll.monthly_salary"), key: "salary", width: 130,
      render: (_, r) => <EditableNum value={r.monthly_salary} disabled={r.is_paid} onSave={(v) => save(r.id, "monthly_salary", v)} />,
    },
    {
      title: t("payroll.working_days"), key: "wd", width: 90,
      render: (_, r) => <EditableNum value={r.working_days} disabled={r.is_paid} style={{ width: 70 }} onSave={(v) => save(r.id, "working_days", v)} />,
    },
    {
      title: t("payroll.days_attended"), dataIndex: "days_attended", key: "att", width: 130, align: "center",
      render: (v, r) => (
        <Button size="small" icon={<TableOutlined />} onClick={() => setTimesheet({ id: r.id, name: r.employee_name })}>
          {v} {t("payroll.days_short")}
        </Button>
      ),
    },
    {
      title: t("payroll.overtime_hours"), dataIndex: "overtime_hours", key: "ot", width: 90, align: "right",
      render: (v) => `${fmt(v)}`,
    },
    {
      title: t("payroll.social_insurance"), key: "soc", width: 120,
      render: (_, r) => <EditableNum value={r.social_insurance} disabled={r.is_paid} onSave={(v) => save(r.id, "social_insurance", v)} />,
    },
    {
      title: t("payroll.taxes"), key: "taxes", width: 110,
      render: (_, r) => <EditableNum value={r.taxes} disabled={r.is_paid} onSave={(v) => save(r.id, "taxes", v)} />,
    },
    {
      title: t("payroll.bonus"), key: "bonus", width: 120,
      render: (_, r) => <EditableNum value={r.bonus} disabled={r.is_paid} onSave={(v) => save(r.id, "bonus", v)} />,
    },
    {
      title: t("payroll.daily_rate"), dataIndex: "daily_rate", key: "daily", width: 100, align: "right",
      render: (v) => <Text type="secondary">{fmt(v)}</Text>,
    },
    {
      title: t("payroll.net_total"), dataIndex: "net_total", key: "net", width: 130, align: "right", fixed: "right",
      render: (v) => <Text strong style={{ color: "#389e0d" }}>{fmt(v)}</Text>,
    },
    {
      title: t("common.actions"), key: "act", width: 120, fixed: "right",
      render: (_, r) => r.is_paid
        ? <Tag color="green">{t("payroll.paid")}</Tag>
        : <Button type="primary" size="small" icon={<DollarOutlined />} onClick={() => { setPayTarget(r); payForm.resetFields(); }}>
            {t("payroll.pay")}
          </Button>,
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: "space-between", width: "100%" }} wrap>
        <Title level={4} style={{ margin: 0 }}>{t("nav.payroll")}</Title>
        <Space wrap>
          <DatePicker picker="month" value={month} allowClear={false} onChange={(v) => v && setMonth(v)} />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>{t("payroll.add_employee")}</Button>
        </Space>
      </Space>

      <Card styles={{ body: { padding: 0 } }}>
        <Table
          rowKey="id"
          size="middle"
          loading={isLoading}
          dataSource={rows}
          columns={columns}
          pagination={false}
          scroll={{ x: 1200 }}
          locale={{ emptyText: t("payroll.no_employees") }}
          summary={() => rows.length ? (
            <Table.Summary fixed>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={9}><Text strong>{t("common.total")}</Text></Table.Summary.Cell>
                <Table.Summary.Cell index={9} align="right">
                  <Text strong style={{ color: "#389e0d" }}>{fmt(data?.totals.net_total)}</Text>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={10} />
              </Table.Summary.Row>
            </Table.Summary>
          ) : null}
        />
      </Card>

      <TimesheetModal
        recordId={timesheet?.id ?? null}
        employeeName={timesheet?.name ?? ""}
        open={!!timesheet}
        onClose={() => setTimesheet(null)}
      />

      {/* Добавить работника */}
      <Modal
        open={addOpen}
        title={t("payroll.add_employee")}
        onCancel={() => setAddOpen(false)}
        onOk={() => addForm.validateFields().then((v) => addMut.mutate(v))}
        confirmLoading={addMut.isPending}
        okText={t("common.save")}
      >
        <Form form={addForm} layout="vertical">
          <Form.Item name="user_id" label={t("payroll.employee")} rules={[{ required: true, message: t("payroll.select_employee") }]}>
            <Select
              showSearch
              optionFilterProp="label"
              placeholder={t("payroll.select_employee")}
              notFoundContent={t("payroll.no_free_users")}
              options={(freeUsers as any[]).map((u) => ({ value: u.user_id, label: u.full_name }))}
              onChange={(val) => {
                const u = (freeUsers as any[]).find((x) => x.user_id === val);
                addForm.setFieldsValue({ position: u?.role ? t(`role.${u.role}`) : undefined });
              }}
            />
          </Form.Item>
          <Form.Item name="position" label={t("payroll.position")}>
            <Input placeholder={t("payroll.position_auto")} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Выплатить */}
      <Modal
        open={!!payTarget}
        title={payTarget ? `${t("payroll.pay")} · ${payTarget.employee_name}` : ""}
        onCancel={() => setPayTarget(null)}
        onOk={() => payForm.validateFields().then((v) => payMut.mutate({
          cash_register_id: v.cash_register_id,
          expense_date: v.expense_date ? v.expense_date.format("YYYY-MM-DD") : undefined,
          cash_rate: needCashRate ? v.cash_rate : undefined,
        }))}
        confirmLoading={payMut.isPending}
        okText={t("payroll.pay")}
      >
        {payTarget && (
          <>
            <p><Text strong style={{ fontSize: 16, color: "#389e0d" }}>{fmt(payTarget.net_total)} CNY</Text> — {t("payroll.net_total")}</p>
            <Form form={payForm} layout="vertical" initialValues={{ expense_date: dayjs() }}>
              <Form.Item name="cash_register_id" label={t("expense.cash_register")} rules={[{ required: true }]}>
                <Select options={(registers as any[]).filter((r) => r.is_active).map((r) => ({ value: r.id, label: `${r.name} (${r.currency})` }))} />
              </Form.Item>
              <Form.Item name="expense_date" label={t("payment.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
              {needCashRate && (
                <Form.Item name="cash_rate" label={`1 ${payRegCur} = ? CNY`} rules={[{ required: true }]}>
                  <InputNumber min={0.000001} step={0.01} precision={6} style={{ width: "100%" }} placeholder={`1 ${payRegCur} = ? CNY`} />
                </Form.Item>
              )}
            </Form>
          </>
        )}
      </Modal>
    </div>
  );
}
