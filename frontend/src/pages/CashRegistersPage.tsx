import { useState } from "react";
import {
  Table, Button, Modal, Form, Input, Select, Space, Tag, Typography,
  Drawer, Descriptions, Badge, Popconfirm, message, Row, Col,
} from "antd";
import { PlusOutlined, HistoryOutlined, EditOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  getCashRegisters, createCashRegister, updateCashRegister,
  getCashTransactions, type CashRegister, type CashTransaction,
} from "../api/cashRegisters";

const { Title, Text } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

const fmt = (v: number, cur: string) =>
  `${Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${cur}`;

export default function CashRegistersPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CashRegister | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedReg, setSelectedReg] = useState<CashRegister | null>(null);
  const [form] = Form.useForm();

  const { data: registers = [], isLoading } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then(r => r.data),
  });

  const { data: transactions = [] } = useQuery({
    queryKey: ["cash-transactions", selectedReg?.id],
    queryFn: () => getCashTransactions(selectedReg!.id, { page_size: 100 }).then(r => r.data),
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

  const openCreate = () => { setEditing(null); form.resetFields(); form.setFieldsValue({ currency: "CNY" }); setModalOpen(true); };
  const openEdit = (reg: CashRegister) => {
    setEditing(reg);
    form.setFieldsValue({ name: reg.name, currency: reg.currency, notes: reg.notes });
    setModalOpen(true);
  };
  const openHistory = (reg: CashRegister) => { setSelectedReg(reg); setDrawerOpen(true); };

  const handleSubmit = (values: any) => {
    if (editing) updateMut.mutate({ id: editing.id, data: values });
    else createMut.mutate(values);
  };

  const txColumns = [
    {
      title: t("common.date"),
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (v: string) => new Date(v).toLocaleString("ru-RU"),
    },
    {
      title: t("cash.direction"),
      dataIndex: "direction",
      key: "direction",
      width: 100,
      render: (v: string) => (
        <Tag color={v === "in" ? "green" : "red"}>
          {v === "in" ? `▲ ${t("payment.direction_in")}` : `▼ ${t("payment.direction_out")}`}
        </Tag>
      ),
    },
    {
      title: t("cash.amount"),
      dataIndex: "amount",
      key: "amount",
      align: "right" as const,
      render: (v: number, row: CashTransaction) => (
        <Text strong style={{ color: row.direction === "in" ? "#389e0d" : "#cf1322" }}>
          {row.direction === "in" ? "+" : "−"}{fmt(v, selectedReg?.currency || "")}
        </Text>
      ),
    },
    {
      title: t("cash.balance_after"),
      dataIndex: "balance_after",
      key: "balance_after",
      align: "right" as const,
      render: (v: number) => <Text>{fmt(v, selectedReg?.currency || "")}</Text>,
    },
    {
      title: t("common.created_by"),
      dataIndex: "created_by_name",
      key: "created_by_name",
    },
    {
      title: t("payment.notes"),
      dataIndex: "notes",
      key: "notes",
      render: (v: string) => v || "—",
    },
  ];

  const regColumns = [
    {
      title: t("cash.name"),
      dataIndex: "name",
      key: "name",
      render: (v: string, row: CashRegister) => (
        <Space>
          <Text strong>{v}</Text>
          <Tag>{row.currency}</Tag>
          {!row.is_active && <Tag color="default">{t("user.blocked")}</Tag>}
        </Space>
      ),
    },
    {
      title: t("cash.balance"),
      dataIndex: "balance",
      key: "balance",
      align: "right" as const,
      render: (v: number, row: CashRegister) => (
        <Text strong style={{ color: v >= 0 ? "#389e0d" : "#cf1322", fontSize: 15 }}>
          {fmt(v, row.currency)}
        </Text>
      ),
    },
    {
      title: t("cash.notes"),
      dataIndex: "notes",
      key: "notes",
      render: (v: string) => v || "—",
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 120,
      render: (_: any, row: CashRegister) => (
        <Space>
          <Button icon={<HistoryOutlined />} size="small" onClick={() => openHistory(row)} />
          <Button icon={<EditOutlined />} size="small" onClick={() => openEdit(row)} />
        </Space>
      ),
    },
  ];

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

      <Table
        columns={regColumns}
        dataSource={registers}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={false}
      />

      {/* Create / Edit modal */}
      <Modal
        open={modalOpen}
        title={editing ? t("cash.edit") : t("cash.add_new")}
        onOk={() => form.validateFields().then(handleSubmit)}
        onCancel={() => { setModalOpen(false); setEditing(null); form.resetFields(); }}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        confirmLoading={createMut.isPending || updateMut.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t("cash.name")} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="currency" label={t("payment.currency")} rules={[{ required: true }]}>
            <Select options={CURRENCIES.map(c => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="notes" label={t("cash.notes")}>
            <Input.TextArea rows={2} />
          </Form.Item>
          {editing && (
            <Form.Item name="is_active" label={t("user.status")}>
              <Select options={[
                { value: true, label: t("user.active") },
                { value: false, label: t("user.blocked") },
              ]} />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* Transactions drawer */}
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
        width={800}
      >
        <Table
          columns={txColumns}
          dataSource={transactions}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 50 }}
        />
      </Drawer>
    </div>
  );
}
