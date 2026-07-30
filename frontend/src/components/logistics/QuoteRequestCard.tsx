import { useState } from "react";
import {
  Card, Descriptions, Button, Tag, Space, Modal, Form, InputNumber,
  Select, Input, message, Popconfirm, Typography, Tooltip,
} from "antd";
import {
  PlusOutlined, CheckCircleFilled, DeleteOutlined, CheckOutlined, EditOutlined,
  DownOutlined, RightOutlined,
} from "@ant-design/icons";
import QuoteRequestFields from "./QuoteRequestFields";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import CounterpartySelect from "../common/CounterpartySelect";
import {
  addSupplierQuote, selectQuote, unselectQuote, deleteSupplierQuote, deleteQuoteRequest,
  updateQuoteRequest,
  type QuoteRequest, type SupplierQuote,
} from "../../api/logisticsQuotes";

const { Text } = Typography;

const fmtNum = (v?: number | null) =>
  v == null ? "—" : Number(v).toLocaleString("ru-RU", { maximumFractionDigits: 3 });

interface Props {
  request: QuoteRequest;
  onChanged: () => void;
  showDelete?: boolean;
}

export default function QuoteRequestCard({ request, onChanged, showDelete = true }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [pending, setPending] = useState<string | null>(request.selected_quote_id ?? null);
  const [quoteModal, setQuoteModal] = useState(false);
  const [quoteForm] = Form.useForm();
  const [editOpen, setEditOpen] = useState(false);
  const [editForm] = Form.useForm();

  const openEdit = () => {
    editForm.setFieldsValue({
      order_number: request.order_number,
      product_name: request.product_name,
      box: request.box ? request.box.split(",").map(s => s.trim()).filter(Boolean) : [],
      dimensions: request.dimensions,
      cargo_value: request.cargo_value,
      client_price: request.client_price ?? undefined,
      weight_kg: request.weight_kg ?? undefined,
      volume_m3: request.volume_m3 ?? undefined,
      destination: request.destination,
      dispatch_place: request.dispatch_place,
    });
    setEditOpen(true);
  };

  const editMut = useMutation({
    mutationFn: (v: any) => updateQuoteRequest(request.id, {
      order_number: v.order_number,
      product_name: v.product_name,
      box: Array.isArray(v.box) ? v.box.join(", ") : v.box,
      dimensions: v.dimensions,
      cargo_value: v.cargo_value,
      client_price: v.client_price ?? undefined,
      weight_kg: v.weight_kg ?? undefined,
      volume_m3: v.volume_m3 ?? undefined,
      destination: v.destination,
      dispatch_place: v.dispatch_place,
    }),
    onSuccess: () => { message.success("✓"); setEditOpen(false); onChanged(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const err = (e: any) => message.error(e.response?.data?.detail || "Error");
  const refreshBadge = () => qc.invalidateQueries({ queryKey: ["quotes-pending-count"] });

  const addMut = useMutation({
    mutationFn: (v: any) => addSupplierQuote(request.id, v),
    onSuccess: () => { message.success("✓"); setQuoteModal(false); quoteForm.resetFields(); onChanged(); },
    onError: err,
  });
  const selectMut = useMutation({
    mutationFn: (quoteId: string) => selectQuote(request.id, quoteId),
    onSuccess: () => { message.success(t("quote.selected_ok")); onChanged(); refreshBadge(); },
    onError: err,
  });
  const unselectMut = useMutation({
    mutationFn: () => unselectQuote(request.id),
    onSuccess: () => { setPending(null); onChanged(); refreshBadge(); },
    onError: err,
  });
  const delQuoteMut = useMutation({
    mutationFn: (quoteId: string) => deleteSupplierQuote(quoteId),
    onSuccess: () => { onChanged(); },
    onError: err,
  });
  const delReqMut = useMutation({
    mutationFn: () => deleteQuoteRequest(request.id),
    onSuccess: () => { message.success("✓"); onChanged(); refreshBadge(); },
    onError: err,
  });

  const unitLabel = (u: string) => u === "per_kg" ? t("quote.per_kg") : t("quote.per_cbm");

  const selected = request.selected_quote_id;
  const pendingChanged = pending && pending !== selected;
  const selectedQuote = request.quotes.find(q => q.id === selected);
  // Свернуть можно только после выбора поставщика; по умолчанию свёрнуто (обработано)
  const [collapsed, setCollapsed] = useState<boolean>(!!selected);

  return (
    <Card
      size="small"
      style={{ marginBottom: 16 }}
      title={
        <Space wrap size={4}>
          {selected && (
            <Button size="small" type="text" style={{ padding: "0 4px" }}
              icon={collapsed ? <RightOutlined /> : <DownOutlined />}
              onClick={() => setCollapsed(c => !c)} />
          )}
          <Text strong>{request.order_number || t("quote.manual_row")}</Text>
          {request.product_name && <Text type="secondary">· {request.product_name}</Text>}
          {collapsed && selectedQuote && (
            <Tag color="green" style={{ marginLeft: 4 }}>
              {selectedQuote.supplier_name} · {selectedQuote.price} {selectedQuote.currency}
              {request.selected_total != null ? ` · ${fmtNum(request.selected_total)}` : ""}
            </Tag>
          )}
        </Space>
      }
      extra={
        <Space size={0}>
          <Button size="small" type="text" icon={<EditOutlined />} onClick={openEdit} />
          {showDelete && (
            <Popconfirm title={t("common.delete") + "?"} onConfirm={() => delReqMut.mutate()}
              okText={t("common.yes")} cancelText={t("common.no")}>
              <Button size="small" type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      }
    >
      {!collapsed && (<>
      <Descriptions size="small" column={{ xs: 1, sm: 2, md: 4 }} style={{ marginBottom: 12 }}>
        <Descriptions.Item label={t("quote.box")}>{request.box || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("quote.dimensions")}>{request.dimensions || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("quote.volume")}>{fmtNum(request.volume_m3)} м³</Descriptions.Item>
        <Descriptions.Item label={t("quote.weight")}>{fmtNum(request.weight_kg)} кг</Descriptions.Item>
        <Descriptions.Item label={t("quote.density")}>{fmtNum(request.density)}</Descriptions.Item>
        <Descriptions.Item label={t("quote.cargo_value")}>{request.cargo_value || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("quote.client_price")}>{fmtNum(request.client_price)}</Descriptions.Item>
        <Descriptions.Item label={t("quote.destination")}>{request.destination || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("quote.dispatch")}>{request.dispatch_place || "—"}</Descriptions.Item>
        <Descriptions.Item label={t("quote.added_by")}>{request.created_by_name || "—"}</Descriptions.Item>
      </Descriptions>

      {/* Плитки поставщиков */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {request.quotes.map((q: SupplierQuote) => {
          const isSelected = q.id === selected;
          const isPending = q.id === pending;
          return (
            <div
              key={q.id}
              onClick={() => setPending(q.id)}
              style={{
                cursor: "pointer",
                minWidth: 150,
                border: isSelected ? "2px solid #52c41a" : isPending ? "2px solid #1677ff" : "1px solid #e0e0e0",
                background: isSelected ? "#f6ffed" : isPending ? "#e6f4ff" : "#fff",
                borderRadius: 8,
                padding: "8px 12px",
                position: "relative",
              }}
            >
              {isSelected && (
                <CheckCircleFilled style={{ color: "#52c41a", position: "absolute", top: 6, right: 6 }} />
              )}
              <div style={{ fontWeight: 600, marginBottom: 2 }}>{q.supplier_name}</div>
              <div style={{ fontSize: 15, color: "#cf1322", fontWeight: 600 }}>
                {q.price} {q.currency} <Text type="secondary" style={{ fontSize: 11 }}>/ {unitLabel(q.price_unit)}</Text>
              </div>
              {q.delivery_days && <div style={{ fontSize: 12 }}>{q.delivery_days}</div>}
              {q.insurance_pct != null && (
                <div style={{ fontSize: 12 }}>{t("quote.insurance")}: {q.insurance_pct}$</div>
              )}
              {q.notes && <div style={{ fontSize: 11, color: "#888" }}>{q.notes}</div>}
              <Popconfirm title={t("common.delete") + "?"}
                onConfirm={(e) => { e?.stopPropagation(); delQuoteMut.mutate(q.id); }}
                onCancel={(e) => e?.stopPropagation()}
                okText={t("common.yes")} cancelText={t("common.no")}>
                <Button size="small" type="text" danger icon={<DeleteOutlined />}
                  style={{ position: "absolute", bottom: 2, right: 2 }}
                  onClick={(e) => e.stopPropagation()} />
              </Popconfirm>
            </div>
          );
        })}

        {/* Добавить предложение */}
        <div
          onClick={() => setQuoteModal(true)}
          style={{
            cursor: "pointer", minWidth: 90, display: "flex", alignItems: "center", justifyContent: "center",
            border: "1px dashed #bbb", borderRadius: 8, padding: "8px 12px", color: "#1677ff",
          }}
        >
          <PlusOutlined /> &nbsp;{t("quote.add_quote")}
        </div>
      </div>

      {/* Подтверждение выбора */}
      <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        {pendingChanged && (
          <Button type="primary" icon={<CheckOutlined />} loading={selectMut.isPending}
            onClick={() => selectMut.mutate(pending!)}>
            {t("quote.confirm_selection")}
          </Button>
        )}
        {selected && !pendingChanged && (
          <Space size={4} wrap>
            <Tag color="green">{t("quote.chosen")}</Tag>
            {request.selected_by_name && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t("quote.selected_by")}: {request.selected_by_name}
              </Text>
            )}
            {request.selected_total != null && (
              <Tooltip title={t("quote.total_hint")}>
                <Tag color="blue">{t("quote.total")}: {fmtNum(request.selected_total)}</Tag>
              </Tooltip>
            )}
            <Button size="small" type="link" onClick={() => unselectMut.mutate()}>
              {t("quote.reset_selection")}
            </Button>
          </Space>
        )}
      </div>
      </>)}

      <Modal
        open={quoteModal}
        title={t("quote.add_quote")}
        onOk={() => quoteForm.validateFields().then(v => addMut.mutate({
          ...v,
          insurance_pct: v.insurance_pct ?? undefined,
        }))}
        onCancel={() => { setQuoteModal(false); quoteForm.resetFields(); }}
        confirmLoading={addMut.isPending}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        destroyOnClose
      >
        <Form form={quoteForm} layout="vertical" className="responsive-form" initialValues={{ price_unit: "per_kg", currency: "USD" }}>
          <Form.Item name="supplier_id" label={t("quote.supplier")} rules={[{ required: true }]}>
            <CounterpartySelect type="supplier" logisticsOnly placeholder={t("quote.supplier")} />
          </Form.Item>
          <Space>
            <Form.Item name="price" label={t("quote.price")} rules={[{ required: true }]}>
              <InputNumber min={0} step={0.1} style={{ width: 130 }} />
            </Form.Item>
            <Form.Item name="price_unit" label={t("quote.unit")} rules={[{ required: true }]}>
              <Select style={{ width: 120 }} options={[
                { value: "per_kg", label: t("quote.per_kg") },
                { value: "per_cbm", label: t("quote.per_cbm") },
              ]} />
            </Form.Item>
            <Form.Item name="currency" label={t("payment.currency")}>
              <Select style={{ width: 90 }} options={["USD", "USDT", "CNY", "RUB"].map(c => ({ value: c, label: c }))} />
            </Form.Item>
          </Space>
          <Form.Item name="delivery_days" label={t("quote.delivery_days")}>
            <Input placeholder="18-22天" />
          </Form.Item>
          <Form.Item name="insurance_pct" label={t("quote.insurance")}>
            <InputNumber min={0} step={0.1} prefix="$" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="notes" label={t("payment.notes")}>
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        open={editOpen}
        title={t("quote.edit_request")}
        onOk={() => editForm.validateFields().then(v => editMut.mutate(v))}
        onCancel={() => setEditOpen(false)}
        confirmLoading={editMut.isPending}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" className="responsive-form">
          <QuoteRequestFields />
        </Form>
      </Modal>
    </Card>
  );
}
