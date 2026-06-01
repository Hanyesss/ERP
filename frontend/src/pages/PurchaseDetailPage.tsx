import { useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button, Card, Col, Descriptions, Popconfirm, Row,
  Space, Statistic, Table, Tabs, Tag, Typography, Upload, message, List,
} from "antd";
import { DeleteOutlined, UploadOutlined, FileOutlined } from "@ant-design/icons";
import { getPurchase, deletePurchase } from "../api/purchases";
import { getPaymentsForPurchase } from "../api/payments";
import apiClient from "../api/client";

const { Title, Text } = Typography;

const STATUS_COLORS: Record<string, string> = { unpaid: "red", partial: "orange", paid: "green" };

const fmtCny = (v: number | null | undefined) =>
  v != null ? v.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

export default function PurchaseDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: purchase, isLoading } = useQuery({
    queryKey: ["purchase", id],
    queryFn: () => getPurchase(id!).then(r => r.data),
    enabled: !!id,
  });

  const { data: purchasePayments } = useQuery({
    queryKey: ["payments-for-purchase", id],
    queryFn: () => getPaymentsForPurchase(id!).then(r => r.data),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePurchase(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["purchases"] });
      message.success("✓");
      navigate("/purchases");
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  // Purchase files — хуки ОБЯЗАТЕЛЬНО до любого return
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: purchaseFiles = [], refetch: refetchFiles } = useQuery({
    queryKey: ["purchase-files", id],
    queryFn: () => apiClient.get(`/api/purchases/${id}/files`).then(r => r.data),
    enabled: !!id,
  });
  const uploadFileMut = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return apiClient.post(`/api/purchases/${id}/files`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    },
    onSuccess: () => { refetchFiles(); message.success(t("common.file_uploaded") || "Файл загружен"); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });
  const deleteFileMut = useMutation({
    mutationFn: (fileId: string) => apiClient.delete(`/api/purchases/${id}/files/${fileId}`),
    onSuccess: () => refetchFiles(),
  });

  if (isLoading || !purchase) return null;

  const tabItems = [
    {
      key: "items",
      label: t("purchase.items"),
      children: (
        <Table
          dataSource={purchase.items}
          rowKey="id"
          size="small"
          pagination={false}
          columns={[
            { title: t("order.title"), dataIndex: "order_number", key: "order_num" },
            { title: t("order.item_name"), dataIndex: "order_item_name", key: "name" },
            { title: t("order.item_quantity"), dataIndex: "quantity", key: "qty", align: "right" as const },
            {
              title: `${t("purchase.cost_price")} (${purchase.currency})`,
              dataIndex: "cost_price", key: "cost_price", align: "right" as const,
              render: (v: number) => fmtCny(v),
            },
            {
              title: `${t("purchase.total")} (${purchase.currency})`,
              key: "total", align: "right" as const,
              render: (_: any, row: any) => fmtCny(Number(row.quantity) * Number(row.cost_price)),
            },
            { title: `${t("purchase.cost_amount_cny")} CNY`, dataIndex: "cost_amount", key: "cny", align: "right" as const,
              render: (v: number) => fmtCny(v) },
          ]}
          summary={() => (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={4} align="right">
                <strong>{t("purchase.total")} ({purchase.currency}):</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={4} align="right">
                <strong>{fmtCny(purchase.total_amount)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={5} align="right">
                <strong>{fmtCny(purchase.total_amount_cny)}</strong>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      ),
    },
    {
      key: "payments",
      label: t("tab_payments") || "Платежи",
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 16, padding: "12px 0", borderBottom: "1px solid #f0f0f0" }}>
            <Col>
              <Statistic title={`${t("payment.total")} CNY`} value={fmtCny(purchase.total_amount_cny)} suffix="CNY"
                valueStyle={{ fontSize: 16 }} />
            </Col>
            <Col>
              <Statistic title={t("purchase.paid_amount")} value={fmtCny(purchase.paid_amount_cny)} suffix="CNY"
                valueStyle={{ fontSize: 16, color: "#3f8600" }} />
            </Col>
            <Col>
              <Statistic title={t("purchase.remaining_amount")} value={fmtCny(purchase.remaining_amount_cny)} suffix="CNY"
                valueStyle={{ fontSize: 16, color: purchase.remaining_amount_cny > 0 ? "#cf1322" : "#3f8600" }} />
            </Col>
            <Col flex="auto" style={{ display: "flex", alignItems: "flex-end", justifyContent: "flex-end" }}>
              {purchase.payment_status !== "paid" && (
                <Button
                  type="primary"
                  onClick={() => navigate(`/payments/new?counterparty_id=${purchase.supplier_id}&direction=out`)}
                >
                  {t("payment.create_for_remaining")} ({fmtCny(purchase.remaining_amount_cny)} CNY)
                </Button>
              )}
            </Col>
          </Row>
          {(purchasePayments || []).length === 0 ? (
            <Text type="secondary">{t("payment.no_payments")}</Text>
          ) : (
            <Table
              dataSource={purchasePayments || []}
              rowKey="id"
              size="small"
              pagination={false}
              columns={[
                { title: t("payment.date"), dataIndex: "payment_date", key: "date", width: 110 },
                { title: t("payment.currency"), dataIndex: "currency", key: "cur", width: 80 },
                { title: t("payment.amount"), key: "amount", align: "right" as const,
                  render: (_: any, row: any) => `${Number(row.amount).toLocaleString("ru-RU", {minimumFractionDigits: 2})} ${row.currency}` },
                { title: `${t("payment.alloc_amount")} CNY`, dataIndex: "alloc_cny", key: "alloc_cny", align: "right" as const,
                  render: (v: string) => Number(v).toLocaleString("ru-RU", {minimumFractionDigits: 2}) },
                { title: t("common.actions"), key: "actions", width: 60,
                  render: (_: any, row: any) => (
                    <Button type="link" size="small" onClick={() => navigate(`/payments/${row.id}`)}>
                      {t("common.open")}
                    </Button>
                  )},
              ]}
            />
          )}
        </div>
      ),
    },
    {
      key: "files",
      label: t("order.files") || "Файлы",
      children: (
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            style={{ display: "none" }}
            onChange={e => {
              const file = e.target.files?.[0];
              if (file) uploadFileMut.mutate(file);
              e.target.value = "";
            }}
          />
          <Button
            icon={<UploadOutlined />}
            onClick={() => fileInputRef.current?.click()}
            loading={uploadFileMut.isPending}
            style={{ marginBottom: 12 }}
          >
            {t("common.upload_file") || "Загрузить файл"}
          </Button>
          <List
            dataSource={purchaseFiles}
            locale={{ emptyText: t("common.no_data") || "Нет файлов" }}
            renderItem={(f: any) => (
              <List.Item
                actions={[
                  <Button
                    key="open"
                    type="link"
                    size="small"
                    href={`/files/${f.file_url}`}
                    target="_blank"
                  >
                    {t("common.open")}
                  </Button>,
                  <Popconfirm
                    key="del"
                    title={t("common.delete") + "?"}
                    onConfirm={() => deleteFileMut.mutate(f.id)}
                    okText={t("common.yes")}
                    cancelText={t("common.no")}
                  >
                    <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  avatar={<FileOutlined />}
                  title={f.file_name}
                  description={`${f.uploaded_by_name} · ${new Date(f.uploaded_at).toLocaleString("ru-RU")}`}
                />
              </List.Item>
            )}
          />
        </div>
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 900 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space align="center">
            <Title level={4} style={{ margin: 0 }}>{purchase.purchase_number}</Title>
            <Tag color={STATUS_COLORS[purchase.payment_status]}>
              {t(`purchase.status_${purchase.payment_status}`)}
            </Tag>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate("/purchases")}>{t("common.back")}</Button>
            {purchase.payment_status !== "paid" && (
              <Popconfirm
                title={t("purchase.delete_confirm")}
                onConfirm={() => deleteMutation.mutate()}
                okText={t("common.yes")}
                cancelText={t("common.no")}
              >
                <Button danger icon={<DeleteOutlined />} loading={deleteMutation.isPending}>
                  {t("common.delete")}
                </Button>
              </Popconfirm>
            )}
          </Space>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label={t("purchase.number")}>{purchase.purchase_number}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.date")}>{purchase.purchase_date}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.supplier")}>{purchase.supplier_name}</Descriptions.Item>
          {purchase.order_number && (
            <Descriptions.Item label={t("order.title")}>
              <Button type="link" style={{ padding: 0, height: "auto" }}
                onClick={() => navigate(`/orders/${purchase.order_id}`)}>
                {purchase.order_number}
              </Button>
            </Descriptions.Item>
          )}
          <Descriptions.Item label={t("purchase.currency")}>{purchase.currency}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.rate_to_cny")}>{Number(purchase.rate_to_cny).toFixed(4)}</Descriptions.Item>
          <Descriptions.Item label={t("purchase.payment_status")}>
            <Tag color={STATUS_COLORS[purchase.payment_status]}>{t(`purchase.status_${purchase.payment_status}`)}</Tag>
          </Descriptions.Item>
          {(purchase as any).created_by_name && (
            <Descriptions.Item label={t("purchase.purchaser")}>
              {(purchase as any).created_by_name}
            </Descriptions.Item>
          )}
          {purchase.notes && (
            <Descriptions.Item label={t("purchase.notes")} span={2}>{purchase.notes}</Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Tabs items={tabItems} />
    </div>
  );
}
