import { useState, useEffect } from "react";
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Typography,
  Drawer, Popconfirm, message, Row, Col, Tabs, InputNumber, DatePicker, Tooltip,
  theme, Checkbox,
} from "antd";
import { PlusOutlined, HistoryOutlined, EditOutlined, SwapOutlined, LockOutlined, DownloadOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import {
  getCashRegisters, createCashRegister, updateCashRegister,
  getCashTransactions, getTransfers, createTransfer, exportCashMovements,
  type CashRegister, type CashTransaction, type CashTransfer,
} from "../api/cashRegisters";
import { useHasAnyRole } from "../hooks/useRole";

const { RangePicker } = DatePicker;

const { Title, Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

const fmt = (v: number | string, cur: string) =>
  `${Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur}`;

export default function CashRegistersPage() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const isAdmin = useHasAnyRole("admin");

  // Режим редактирования/создания кассы
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CashRegister | null>(null);
  const [form] = Form.useForm();

  // Drawer истории кассы
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedReg, setSelectedReg] = useState<CashRegister | null>(null);

  // Экспорт движения средств
  const [exportRange, setExportRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportIds, setExportIds] = useState<string[]>([]);
  const [exporting, setExporting] = useState(false);

  // Модал перевода
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferFrom, setTransferFrom] = useState<CashRegister | null>(null);
  const [transferForm] = Form.useForm();
  const fromAmount: number = Form.useWatch("from_amount", transferForm) || 0;
  const exchangeRate: number = Form.useWatch("exchange_rate", transferForm) || 1;

  // Автовычисление суммы получения
  useEffect(() => {
    if (fromAmount > 0 && exchangeRate > 0) {
      transferForm.setFieldValue("to_amount", parseFloat((fromAmount * exchangeRate).toFixed(4)));
    }
  }, [fromAmount, exchangeRate, transferForm]);

  const { data: registers = [], isLoading } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then(r => r.data),
  });

  const { data: transactions = [] } = useQuery({
    queryKey: ["cash-transactions", selectedReg?.id],
    queryFn: () => getCashTransactions(selectedReg!.id, { page_size: 100 }).then(r => r.data),
    enabled: !!selectedReg,
  });

  const { data: transfers = [] } = useQuery({
    queryKey: ["cash-transfers", selectedReg?.id],
    queryFn: () => getTransfers({ register_id: selectedReg!.id }).then(r => r.data),
    enabled: !!selectedReg,
  });

  const createMut = useMutation({
    mutationFn: createCashRegister,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cash-registers"] }); setModalOpen(false); form.resetFields(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateCashRegister(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cash-registers"] }); setModalOpen(false); setEditing(null); form.resetFields(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const transferMut = useMutation({
    mutationFn: createTransfer,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cash-registers"] });
      qc.invalidateQueries({ queryKey: ["cash-transactions"] });
      qc.invalidateQueries({ queryKey: ["cash-transfers"] });
      message.success(t("cash.transfer_done") || "Перевод выполнен");
      setTransferOpen(false);
      transferForm.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const openCreate = () => { setEditing(null); form.resetFields(); form.setFieldsValue({ currency: "CNY", initial_balance: 0 }); setModalOpen(true); };
  const openEdit = (reg: CashRegister) => { setEditing(reg); form.setFieldsValue({ name: reg.name, currency: reg.currency, notes: reg.notes, initial_balance: reg.initial_balance }); setModalOpen(true); };
  const openHistory = (reg: CashRegister) => { setSelectedReg(reg); setDrawerOpen(true); };
  const openTransfer = (reg: CashRegister) => {
    setTransferFrom(reg);
    transferForm.resetFields();
    transferForm.setFieldsValue({ from_register_id: reg.id, exchange_rate: 1, transfer_date: dayjs() });
    setTransferOpen(true);
  };

  const handleSubmit = (values: any) => {
    if (editing) updateMut.mutate({ id: editing.id, data: values });
    else createMut.mutate(values);
  };

  const handleTransfer = (values: any) => {
    transferMut.mutate({
      from_register_id: values.from_register_id,
      to_register_id: values.to_register_id,
      from_amount: values.from_amount,
      to_amount: values.to_amount,
      exchange_rate: values.exchange_rate,
      transfer_date: values.transfer_date.format("YYYY-MM-DD"),
      notes: values.notes,
    });
  };

  // Отмены: payment_cancel, expense_cancel, data_fix
  const CANCEL_OPS = new Set(["payment_cancel", "expense_cancel", "data_fix"]);

  const txColumns = [
    { title: t("common.date"), dataIndex: "created_at", key: "d", width: 155,
      render: (v: string) => new Date(v).toLocaleString("ru-RU") },
    { title: t("cash.direction"), key: "dir", width: 160,
      render: (_: any, row: CashTransaction) => {
        const isCancel = row.operation_type ? CANCEL_OPS.has(row.operation_type) : false;
        const opLabel = row.operation_type
          ? (t(`cash.op.${row.operation_type}`, { defaultValue: "" }) || row.operation_type)
          : (row.direction === "in" ? t("payment.direction_in") : t("payment.direction_out"));
        return (
          <Space size={4} wrap>
            <Tag color={!row.is_active ? "default" : isCancel ? "red" : row.direction === "in" ? "green" : "orange"}
                 style={isCancel ? { border: "1px solid #ff4d4f" } : undefined}>
              {row.direction === "in" ? "▲" : "▼"} {opLabel}
            </Tag>
            {!row.is_active && <Tag color="default" style={{ fontSize: 10 }}>{t("common.cancelled") || "отменена"}</Tag>}
          </Space>
        );
      }},
    { title: t("cash.amount"), dataIndex: "amount", key: "a", align: "right" as const, width: 150,
      render: (v: number, row: CashTransaction) => {
        const isCancel = row.operation_type ? CANCEL_OPS.has(row.operation_type) : false;
        return (
          <Text strong style={{
            whiteSpace: "nowrap",
            color: !row.is_active ? "#bfbfbf" : isCancel ? "#ff4d4f" : row.direction === "in" ? "#389e0d" : "#cf1322",
            textDecoration: !row.is_active ? "line-through" : undefined,
          }}>
            {row.direction === "in" ? "+" : "−"}{fmt(v, selectedReg?.currency || "")}
          </Text>
        );
      }},
    { title: t("cash.balance_after"), dataIndex: "balance_after", key: "b", align: "right" as const, width: 150,
      render: (v: number, row: CashTransaction) => (
        <Text style={{ whiteSpace: "nowrap", color: row.is_active ? undefined : "#bfbfbf" }}>{fmt(v, selectedReg?.currency || "")}</Text>
      )},
    { title: t("payment.notes"), key: "n",
      render: (_: any, row: CashTransaction) => row.notes || "—" },
    { title: "Причина", key: "reason", width: 140,
      render: (_: any, row: CashTransaction) => {
        const r = row.reason;
        if (!r) return "—";
        const truncated = r.length > 18 ? r.slice(0, 17) + "…" : r;
        return r.length > 18
          ? <Tooltip title={r}><span style={{ cursor: "default" }}>{truncated}</span></Tooltip>
          : <span>{r}</span>;
      }},
    { title: t("common.created_by"), dataIndex: "created_by_name", key: "who", width: 130 },
  ];

  const trColumns = [
    { title: t("common.date"), dataIndex: "transfer_date", key: "d", width: 110 },
    { title: t("cash.from"), key: "from", render: (_: any, r: CashTransfer) =>
        <Text>{r.from_register_name} <Tag>{r.from_currency}</Tag></Text> },
    { title: t("cash.to"), key: "to", render: (_: any, r: CashTransfer) =>
        <Text>{r.to_register_name} <Tag>{r.to_currency}</Tag></Text> },
    { title: t("cash.sent"), key: "sent", align: "right" as const,
      render: (_: any, r: CashTransfer) => <Text type="danger">−{fmt(r.from_amount, r.from_currency)}</Text> },
    { title: t("cash.received"), key: "recv", align: "right" as const,
      render: (_: any, r: CashTransfer) => <Text type="success">+{fmt(r.to_amount, r.to_currency)}</Text> },
    { title: t("cash.rate"), dataIndex: "exchange_rate", key: "rate", width: 90,
      render: (v: number) => Number(v).toFixed(4) },
    { title: t("common.created_by"), dataIndex: "created_by_name", key: "who" },
    { title: t("payment.notes"), dataIndex: "notes", key: "n", render: (v: string) => v || "—" },
  ];

  const regColumns = [
    { title: t("cash.name"), dataIndex: "name", key: "name",
      render: (v: string, row: CashRegister) => (
        <Space>
          <Text strong>{v}</Text>
          <Tag>{row.currency}</Tag>
          {!row.is_active && <Tag color="default">{t("user.blocked")}</Tag>}
        </Space>
      )},
    { title: t("cash.balance"), key: "balance", align: "right" as const,
      render: (_: any, row: CashRegister) => (
        <Space direction="vertical" size={0} style={{ textAlign: "right" }}>
          <Text strong style={{ color: Number(row.balance) >= 0 ? "#389e0d" : "#cf1322", fontSize: 15 }}>
            {fmt(row.balance, row.currency)}
          </Text>
          {Number(row.initial_balance) !== 0 && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              нач. {fmt(row.initial_balance, row.currency)}
            </Text>
          )}
        </Space>
      )},
    { title: t("cash.notes"), dataIndex: "notes", key: "notes", render: (v: string) => v || "—" },
    { title: t("common.actions"), key: "actions", width: 140,
      render: (_: any, row: CashRegister) => (
        <Space>
          <Button icon={<HistoryOutlined />} size="small" title={t("cash.history")} onClick={() => openHistory(row)} />
          <Button icon={<SwapOutlined />} size="small" title={t("cash.transfer")} type="primary" ghost onClick={() => openTransfer(row)} />
          <Button icon={<EditOutlined />} size="small" onClick={() => openEdit(row)} />
        </Space>
      )},
  ];

  const toOptions = registers.filter(r => r.id !== transferFrom?.id && r.is_active)
    .map(r => ({ value: r.id, label: `${r.name} (${r.currency})` }));

  // Шаг 1: даты выбраны → открыть выбор кошельков (по умолчанию все активные)
  const openExportModal = () => {
    if (!exportRange?.[0] || !exportRange?.[1]) {
      message.warning(t("cash.export_pick_dates"));
      return;
    }
    setExportIds(registers.filter(r => r.is_active).map(r => r.id));
    setExportModalOpen(true);
  };

  // Шаг 2: кошельки выбраны → скачать Excel
  const doExport = async () => {
    if (!exportIds.length) { message.warning(t("cash.export_pick_wallets")); return; }
    setExporting(true);
    try {
      await exportCashMovements({
        date_from: exportRange![0].format("YYYY-MM-DD"),
        date_to: exportRange![1].format("YYYY-MM-DD"),
        register_ids: exportIds,
        lang: i18n.language,
      });
      setExportModalOpen(false);
    } catch {
      message.error(t("common.error") || "Error");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={4} style={{ margin: 0 }}>{t("nav.cash_registers")}</Title></Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            {t("cash.add_new")}
          </Button>
        </Col>
      </Row>

      {/* Панель экспорта движения средств */}
      <Space wrap style={{ marginBottom: 16 }}>
        <RangePicker value={exportRange} onChange={v => setExportRange(v as any)} />
        <Button icon={<DownloadOutlined />} onClick={openExportModal}>
          {t("cash.export_movements")}
        </Button>
      </Space>

      <Table columns={regColumns} dataSource={registers} rowKey="id" scroll={{ x: "max-content" }} loading={isLoading} size="small" pagination={false} />

      {/* Модал выбора кошельков для экспорта */}
      <Modal
        open={exportModalOpen}
        title={t("cash.export_select_wallets")}
        onOk={doExport}
        onCancel={() => setExportModalOpen(false)}
        okText={t("common.confirm")}
        cancelText={t("common.cancel")}
        confirmLoading={exporting}
      >
        <Checkbox
          indeterminate={exportIds.length > 0 && exportIds.length < registers.length}
          checked={exportIds.length === registers.length && registers.length > 0}
          onChange={e => setExportIds(e.target.checked ? registers.map(r => r.id) : [])}
          style={{ marginBottom: 8 }}
        >
          {t("common.all")}
        </Checkbox>
        <div style={{ maxHeight: 320, overflowY: "auto", borderTop: "1px solid #f0f0f0", paddingTop: 8 }}>
          <Checkbox.Group
            value={exportIds}
            onChange={vals => setExportIds(vals as string[])}
            style={{ display: "flex", flexDirection: "column", gap: 8 }}
            options={registers.map(r => ({
              value: r.id,
              label: `${r.name} (${r.currency})${r.is_active ? "" : " — " + t("cash.inactive")}`,
            }))}
          />
        </div>
      </Modal>

      {/* Create / Edit modal */}
      <Modal open={modalOpen} title={editing ? t("cash.edit") : t("cash.add_new")}
        onOk={() => form.validateFields().then(handleSubmit)}
        onCancel={() => { setModalOpen(false); setEditing(null); form.resetFields(); }}
        okText={t("common.save")} cancelText={t("common.cancel")}
        confirmLoading={createMut.isPending || updateMut.isPending} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t("cash.name")} rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="currency" label={t("payment.currency")} rules={[{ required: true }]}>
            <Select options={CURRENCIES.map(c => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="notes" label={t("cash.notes")}><Input.TextArea rows={2} /></Form.Item>

          {/* Начальный баланс — только admin */}
          {isAdmin ? (
            <Form.Item
              name="initial_balance"
              label={
                <Space size={4}>
                  <span>Начальный баланс</span>
                  <Tooltip title="Сумма, с которой касса начинает работу. Влияет на текущий баланс. Только admin.">
                    <LockOutlined style={{ color: "#faad14", fontSize: 12 }} />
                  </Tooltip>
                </Space>
              }
            >
              <InputNumber style={{ width: "100%" }} step={0.01} precision={2} />
            </Form.Item>
          ) : editing ? (
            <Form.Item label="Начальный баланс">
              <InputNumber style={{ width: "100%" }} disabled value={editing.initial_balance} />
            </Form.Item>
          ) : null}

          {editing && (
            <Form.Item name="is_active" label={t("user.status")}>
              <Select options={[{ value: true, label: t("user.active") }, { value: false, label: t("user.blocked") }]} />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* Transfer modal */}
      <Modal
        open={transferOpen}
        title={<Space><SwapOutlined />{t("cash.transfer_title") || "Перевод между кассами"}</Space>}
        onOk={() => transferForm.validateFields().then(handleTransfer)}
        onCancel={() => { setTransferOpen(false); transferForm.resetFields(); }}
        okText={t("cash.do_transfer") || "Перевести"}
        cancelText={t("common.cancel")}
        confirmLoading={transferMut.isPending}
        destroyOnClose
      >
        <Form form={transferForm} layout="vertical">
          <Form.Item name="from_register_id" label={t("cash.from")} rules={[{ required: true }]}>
            <Select
              options={registers.filter(r => r.is_active).map(r => ({ value: r.id, label: `${r.name} (${r.currency})` }))}
              onChange={v => { const r = registers.find(x => x.id === v); setTransferFrom(r || null); }}
            />
          </Form.Item>

          <Form.Item name="to_register_id" label={t("cash.to")} rules={[{ required: true }]}>
            <Select options={toOptions} placeholder={t("cash.select_register")} />
          </Form.Item>

          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="from_amount" label={t("cash.send_amount") || `Сумма списания${transferFrom ? ` (${transferFrom.currency})` : ""}`} rules={[{ required: true }, { type: "number", min: 0.01 }]}>
                <InputNumber style={{ width: "100%" }} min={0} step={0.01} precision={2} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="exchange_rate" label={t("cash.exchange_rate") || "Курс конвертации"} rules={[{ required: true }]}>
                <InputNumber style={{ width: "100%" }} min={0.000001} step={0.01} precision={6} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="to_amount" label={t("cash.receive_amount") || "Сумма зачисления"} rules={[{ required: true }, { type: "number", min: 0.01 }]}>
            <InputNumber style={{ width: "100%" }} min={0} step={0.01} precision={4} />
          </Form.Item>

          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="transfer_date" label={t("common.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="notes" label={t("payment.notes")}>
                <Input placeholder={t("payment.notes")} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* History Drawer */}
      <Drawer
        title={
          <Space>
            <Text>{selectedReg?.name}</Text>
            <Tag>{selectedReg?.currency}</Tag>
            <Text strong style={{ color: "#389e0d" }}>
              {t("cash.balance")}: {selectedReg ? fmt(selectedReg.balance, selectedReg.currency) : "—"}
            </Text>
          </Space>
        }
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={900}
      >
        <Tabs
          items={[
            {
              key: "transactions",
              label: t("cash.transactions") || "Транзакции",
              children: (
                <Table columns={txColumns} dataSource={transactions} rowKey="id" size="small" pagination={{ pageSize: 50 }} scroll={{ x: "max-content" }} />
              ),
            },
            {
              key: "transfers",
              label: t("cash.transfers") || "Переводы",
              children: (
                <Table columns={trColumns} dataSource={transfers} rowKey="id" size="small" pagination={{ pageSize: 50 }} scroll={{ x: "max-content" }} />
              ),
            },
          ]}
        />
      </Drawer>
    </div>
  );
}
