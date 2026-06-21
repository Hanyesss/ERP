import { useState } from "react";
import { Table, Button, Input, Select, Tag, Space, Popconfirm, Row, Col, message, Tooltip, Spin, Typography } from "antd";
import { EditOutlined, DeleteOutlined, LinkOutlined, WalletOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import type { Counterparty, CounterpartyFormData } from "../../types/counterparty";
import { getCounterparties, createCounterparty, updateCounterparty, deleteCounterparty, createSiteAccount, linkSiteAccount, updateSiteCredentials } from "../../api/counterparties";
import CounterpartyForm, { type CounterpartyFormValues } from "./CounterpartyForm";
import { getCounterpartyTronTokBalance } from "../../api/trontok";

const { Text } = Typography;

const TYPE_COLORS: Record<string, string> = {
  client: "blue",
  supplier: "orange",
  both: "purple",
  partner: "magenta",
};

function TronTokBalanceRow({ counterpartyId }: { counterpartyId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["trontok-balance", counterpartyId],
    queryFn: () => getCounterpartyTronTokBalance(counterpartyId).then(r => r.data),
    staleTime: 60_000,
    retry: 1,
  });

  if (isLoading) return <Spin size="small" />;
  if (isError) return <Text type="danger">Ошибка загрузки (TronTok недоступен)</Text>;
  if (!data?.trontok_linked) return <Text type="secondary">Кошелёк TronTok не зарегистрирован</Text>;
  if (!data.balance) return <Text type="secondary">Баланс недоступен</Text>;

  const bal = data.balance;
  const available = Number(bal.available ?? 0);
  const frozen = Number(bal.frozen ?? 0);
  return (
    <Space size={24}>
      <div>
        <Text type="secondary" style={{ fontSize: 12 }}>Доступно</Text>
        <div><Text strong style={{ fontSize: 16 }}>{available.toFixed(2)}</Text> <Text type="secondary">USDT</Text></div>
      </div>
      {frozen > 0 && (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>Заморожено</Text>
          <div><Text>{frozen.toFixed(2)}</Text> <Text type="secondary">USDT</Text></div>
        </div>
      )}
    </Space>
  );
}

interface Props {
  forcedType?: "client" | "supplier";
}

export default function CounterpartyTable({ forcedType }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState(forcedType ?? "all");
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Counterparty | null>(null);

  const effectiveType = forcedType ?? typeFilter;

  const { data, isLoading } = useQuery({
    queryKey: ["counterparties", search, effectiveType, page],
    queryFn: () => getCounterparties({ search: search || undefined, type: effectiveType, page, page_size: 20 }).then(r => r.data),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["counterparties"] });

  const createMutation = useMutation({
    mutationFn: createCounterparty,
    onSuccess: async (res, variables) => {
      const vals = variables as CounterpartyFormValues;
      if (vals.create_site_account && vals.site_login && vals.site_password) {
        try {
          await createSiteAccount(res.data.id, { login: vals.site_login, password: vals.site_password });
          message.success(t("counterparty.site_account_created"));
        } catch (e: any) {
          message.warning(t("counterparty.site_account_error", { error: e.response?.data?.detail || String(e) }));
        }
      }
      invalidate();
      setFormOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<CounterpartyFormData> }) => updateCounterparty(id, data),
    onSuccess: async (_, { id, data }) => {
      const vals = data as CounterpartyFormValues;
      if (vals.current_site_login && (vals.new_site_login || vals.new_site_password)) {
        try {
          await updateSiteCredentials(id, {
            current_login: vals.current_site_login,
            new_login: vals.new_site_login || undefined,
            new_password: vals.new_site_password || undefined,
          });
          message.success(t("counterparty.site_credentials_updated"));
        } catch (e: any) {
          message.warning(t("counterparty.site_account_error", { error: e.response?.data?.detail || String(e) }));
        }
      }
      invalidate();
      setFormOpen(false);
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCounterparty,
    onSuccess: invalidate,
  });

  const linkMutation = useMutation({
    mutationFn: (id: string) => linkSiteAccount(id),
    onSuccess: () => message.success(t("counterparty.site_account_linked")),
    onError: (e: any) => message.error(t("counterparty.site_account_error", { error: e.response?.data?.detail || String(e) })),
  });

  const handleSubmit = (formData: CounterpartyFormValues) => {
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: formData });
    } else {
      createMutation.mutate(formData as CounterpartyFormData);
    }
  };

  const openCreate = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (cp: Counterparty) => { setEditing(cp); setFormOpen(true); };

  const columns: ColumnsType<Counterparty> = [
    {
      title: t("counterparty.name"),
      dataIndex: "name",
      key: "name",
      render: (name: string, row: Counterparty) => (
        <div>
          <Space size={4}>
            <span>{name}</span>
            {(row as any).trontok_linked && (
              <Tooltip title="TronTok кошелёк привязан">
                <Tag icon={<WalletOutlined />} color="geekblue" style={{ marginLeft: 4, fontSize: 11 }}>
                  TronTok
                </Tag>
              </Tooltip>
            )}
          </Space>
          {row.name_cn && <div style={{ color: "#888", fontSize: 12 }}>{row.name_cn}</div>}
        </div>
      ),
    },
    {
      title: t("counterparty.type"),
      dataIndex: "type",
      key: "type",
      render: (type: string) => (
        <Tag color={TYPE_COLORS[type]}>{t(`counterparty.type_${type}`)}</Tag>
      ),
    },
    {
      title: t("counterparty.default_currency"),
      dataIndex: "default_currency",
      key: "default_currency",
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 130,
      render: (_: unknown, row: Counterparty) => {
        const canSync = row.code && (row.type === "client" || row.type === "both" || row.type === "partner");
        return (
          <Space>
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => openEdit(row)}
            />
            {canSync && (
              <Tooltip title={t("counterparty.link_site_account")}>
                <Popconfirm
                  title={t("counterparty.link_site_confirm")}
                  onConfirm={() => linkMutation.mutate(row.id)}
                  okText={t("common.yes")}
                  cancelText={t("common.no")}
                >
                  <Button
                    icon={<LinkOutlined />}
                    size="small"
                    loading={linkMutation.isPending}
                  />
                </Popconfirm>
              </Tooltip>
            )}
            <Popconfirm
              title={t("counterparty.delete_confirm")}
              onConfirm={() => deleteMutation.mutate(row.id)}
              okText={t("common.yes")}
              cancelText={t("common.no")}
            >
              <Button icon={<DeleteOutlined />} size="small" danger />
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  const typeOptions = [
    { value: "all", label: t("common.all") },
    { value: "client", label: t("counterparty.type_client") },
    { value: "supplier", label: t("counterparty.type_supplier") },
    { value: "both", label: t("counterparty.type_both") },
    { value: "partner", label: t("counterparty.type_partner") },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space>
            <Input.Search
              placeholder={t("counterparty.search_placeholder")}
              allowClear
              style={{ width: 280 }}
              onSearch={val => { setSearch(val); setPage(1); }}
              onChange={e => { if (!e.target.value) { setSearch(""); setPage(1); } }}
            />
            {!forcedType && (
              <Select
                value={typeFilter}
                onChange={val => { setTypeFilter(val); setPage(1); }}
                options={typeOptions}
                style={{ width: 180 }}
              />
            )}
          </Space>
        </Col>
        <Col>
          <Button type="primary" onClick={openCreate}>
            {t("counterparty.add_new")}
          </Button>
        </Col>
      </Row>

      <Table scroll={{ x: "max-content" }}
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        expandable={{
          rowExpandable: (row) => !!(row.code) && (row.type === "client" || row.type === "both"),
          expandedRowRender: (row) => (
            <div style={{ padding: "8px 16px" }}>
              <Space>
                <WalletOutlined style={{ color: "#1677ff" }} />
                <Text strong style={{ color: "#1677ff" }}>TronTok баланс</Text>
              </Space>
              <div style={{ marginTop: 6 }}>
                <TronTokBalanceRow counterpartyId={row.id} />
              </div>
            </div>
          ),
        }}
        pagination={{
          current: page,
          total: data?.total ?? 0,
          pageSize: 20,
          onChange: setPage,
          showTotal: (total) => `${total}`,
        }}
      />

      <CounterpartyForm
        open={formOpen}
        editing={editing}
        onClose={() => { setFormOpen(false); setEditing(null); }}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
        forcedType={forcedType}
      />
    </div>
  );
}
