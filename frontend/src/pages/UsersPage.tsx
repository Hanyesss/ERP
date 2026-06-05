import { useState, useCallback } from "react";
import {
  Table, Button, Space, Tag, Select, Input, Switch, Modal,
  Form, Checkbox, Typography, message, Popconfirm, Tooltip,
} from "antd";
import {
  PlusOutlined, LockOutlined, UnlockOutlined, EditOutlined, KeyOutlined, DeleteOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  fetchUsers, createUser, updateUser, resetPassword, toggleActive, deleteUser,
  UserListItem, UserRole, UserLang,
} from "../api/users";

const { Text } = Typography;

const ALL_ROLES: UserRole[] = ["employee", "seller", "manager", "purchaser", "accountant", "admin", "partner"];
const ALL_LANGS: UserLang[] = ["ru", "zh"];

function RoleTag({ role }: { role: UserRole }) {
  const { t } = useTranslation();
  const colors: Record<UserRole, string> = {
    admin: "red",
    seller: "blue",
    manager: "cyan",
    purchaser: "green",
    accountant: "purple",
    partner: "magenta",
    employee: "default",
  };
  return <Tag color={colors[role]}>{t(`role.${role}`)}</Tag>;
}

interface FilterState {
  role?: string;
  is_active?: boolean;
  search?: string;
}

export default function UsersPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [filter, setFilter] = useState<FilterState>({});
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserListItem | null>(null);
  const [pwdModalOpen, setPwdModalOpen] = useState(false);
  const [pwdTarget, setPwdTarget] = useState<UserListItem | null>(null);
  const [newPwdResult, setNewPwdResult] = useState<string | null>(null);

  const [form] = Form.useForm();
  const [pwdForm] = Form.useForm();

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users", filter],
    queryFn: () => fetchUsers(filter),
  });

  const createMut = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setModalOpen(false);
      form.resetFields();
      message.success(t("user.created"));
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Error";
      message.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateUser(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setModalOpen(false);
      form.resetFields();
      setEditingUser(null);
      message.success(t("user.updated"));
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Error";
      message.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    },
  });

  const toggleMut = useMutation({
    mutationFn: (id: string) => toggleActive(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
    onError: (e: any) => {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Error";
      message.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      message.success(t("user.deleted"));
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Error";
      message.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    },
  });

  const resetPwdMut = useMutation({
    mutationFn: ({ id, password }: { id: string; password?: string }) =>
      resetPassword(id, { password: password || undefined }),
    onSuccess: (res) => {
      setNewPwdResult(res.new_password);
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Error";
      message.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    },
  });

  const openCreate = useCallback(() => {
    setEditingUser(null);
    form.resetFields();
    form.setFieldsValue({ lang: "ru", is_active: true, roles: [] });
    setModalOpen(true);
  }, [form]);

  const openEdit = useCallback((user: UserListItem) => {
    setEditingUser(user);
    form.setFieldsValue({
      full_name: user.full_name,
      login: user.login,
      lang: user.lang,
      roles: user.roles,
      is_active: user.is_active,
    });
    setModalOpen(true);
  }, [form]);

  const openResetPwd = useCallback((user: UserListItem) => {
    setPwdTarget(user);
    setNewPwdResult(null);
    pwdForm.resetFields();
    setPwdModalOpen(true);
  }, [pwdForm]);

  const handleFormSubmit = async () => {
    const values = await form.validateFields();
    if (editingUser) {
      const patch: any = {
        full_name: values.full_name,
        login: values.login,
        lang: values.lang,
        roles: values.roles,
        is_active: values.is_active,
      };
      if (values.password) patch.password = values.password;
      updateMut.mutate({ id: editingUser.id, data: patch });
    } else {
      createMut.mutate({
        full_name: values.full_name,
        login: values.login,
        password: values.password,
        lang: values.lang,
        roles: values.roles,
        is_active: values.is_active ?? true,
      });
    }
  };

  const handlePwdSubmit = async () => {
    const values = await pwdForm.validateFields();
    resetPwdMut.mutate({ id: pwdTarget!.id, password: values.password || undefined });
  };

  const handleGeneratePwd = () => {
    resetPwdMut.mutate({ id: pwdTarget!.id, password: undefined });
  };

  const copyToClipboard = () => {
    if (newPwdResult) {
      navigator.clipboard.writeText(newPwdResult);
      message.success(t("user.password_copied"));
    }
  };

  const columns = [
    {
      title: t("user.full_name"),
      dataIndex: "full_name",
      key: "full_name",
      render: (v: string, row: UserListItem) => (
        <Space direction="vertical" size={0}>
          <Text strong={!row.is_active ? false : true}
            style={!row.is_active ? { color: "#999" } : undefined}>
            {v}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{row.login}</Text>
        </Space>
      ),
    },
    {
      title: t("user.roles"),
      dataIndex: "roles",
      key: "roles",
      render: (roles: UserRole[]) => (
        <Space wrap size={4}>
          {roles.map((r) => <RoleTag key={r} role={r} />)}
        </Space>
      ),
    },
    {
      title: t("user.language"),
      dataIndex: "lang",
      key: "lang",
      width: 90,
      render: (v: string) => v.toUpperCase(),
    },
    {
      title: t("user.status"),
      dataIndex: "is_active",
      key: "is_active",
      width: 110,
      render: (v: boolean) => (
        <Tag color={v ? "green" : "default"}>
          {v ? t("user.active") : t("user.blocked")}
        </Tag>
      ),
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 160,
      render: (_: any, row: UserListItem) => (
        <Space>
          <Tooltip title={t("common.edit")}>
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => openEdit(row)}
            />
          </Tooltip>
          <Tooltip title={t("user.reset_password")}>
            <Button
              icon={<KeyOutlined />}
              size="small"
              onClick={() => openResetPwd(row)}
            />
          </Tooltip>
          <Tooltip title={row.is_active ? t("user.block") : t("user.unblock")}>
            <Popconfirm
              title={row.is_active ? t("user.block_confirm") : t("user.unblock_confirm")}
              onConfirm={() => toggleMut.mutate(row.id)}
              okText={t("common.yes")}
              cancelText={t("common.cancel")}
            >
              <Button
                icon={row.is_active ? <LockOutlined /> : <UnlockOutlined />}
                size="small"
                danger={row.is_active}
              />
            </Popconfirm>
          </Tooltip>
          <Tooltip title={t("user.delete")}>
            <Popconfirm
              title={t("user.delete_confirm")}
              onConfirm={() => deleteMut.mutate(row.id)}
              okText={t("common.yes")}
              cancelText={t("common.cancel")}
              okButtonProps={{ danger: true }}
            >
              <Button icon={<DeleteOutlined />} size="small" danger />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t("nav.users")}
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          {t("user.add_new")}
        </Button>
      </div>

      {/* Filters */}
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder={t("user.search_placeholder")}
          allowClear
          style={{ width: 220 }}
          onSearch={(v) => setFilter((f) => ({ ...f, search: v || undefined }))}
          onChange={(e) => !e.target.value && setFilter((f) => ({ ...f, search: undefined }))}
        />
        <Select
          placeholder={t("user.filter_role")}
          allowClear
          style={{ width: 160 }}
          options={ALL_ROLES.map((r) => ({ value: r, label: t(`role.${r}`) }))}
          onChange={(v) => setFilter((f) => ({ ...f, role: v }))}
        />
        <Select
          placeholder={t("user.filter_status")}
          allowClear
          style={{ width: 150 }}
          options={[
            { value: "true", label: t("user.active") },
            { value: "false", label: t("user.blocked") },
          ]}
          onChange={(v) =>
            setFilter((f) => ({
              ...f,
              is_active: v === undefined ? undefined : v === "true",
            }))
          }
        />
      </Space>

      <Table scroll={{ x: "max-content" }}
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        size="small"
      />

      {/* Create / Edit Modal */}
      <Modal
        open={modalOpen}
        title={editingUser ? t("user.edit_title") : t("user.create_title")}
        onCancel={() => { setModalOpen(false); setEditingUser(null); form.resetFields(); }}
        onOk={handleFormSubmit}
        confirmLoading={createMut.isPending || updateMut.isPending}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="full_name"
            label={t("user.full_name")}
            rules={[{ required: true, message: t("validation.required") }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            name="login"
            label={t("user.login")}
            rules={[{ required: true, message: t("validation.required") }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            name="password"
            label={editingUser ? t("user.new_password_optional") : t("user.password")}
            rules={[
              { required: !editingUser, message: t("validation.required") },
              { min: 6, message: t("user.password_min_length") },
            ]}
          >
            <Input.Password placeholder={editingUser ? t("user.password_leave_empty") : undefined} />
          </Form.Item>

          <Form.Item
            name="lang"
            label={t("user.language")}
            rules={[{ required: true }]}
          >
            <Select options={ALL_LANGS.map((l) => ({ value: l, label: l.toUpperCase() }))} />
          </Form.Item>

          <Form.Item
            name="roles"
            label={t("user.roles")}
            rules={[
              { required: true, message: t("validation.required") },
              {
                validator: (_, value) =>
                  value && value.length > 0
                    ? Promise.resolve()
                    : Promise.reject(new Error(t("user.roles_required"))),
              },
            ]}
          >
            <Checkbox.Group>
              <Space wrap>
                {ALL_ROLES.map((r) => (
                  <Checkbox key={r} value={r}>
                    {t(`role.${r}`)}
                  </Checkbox>
                ))}
              </Space>
            </Checkbox.Group>
          </Form.Item>

          <Form.Item name="is_active" label={t("user.status")} valuePropName="checked">
            <Switch
              checkedChildren={t("user.active")}
              unCheckedChildren={t("user.blocked")}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal
        open={pwdModalOpen}
        title={`${t("user.reset_password")}: ${pwdTarget?.full_name}`}
        onCancel={() => { setPwdModalOpen(false); setNewPwdResult(null); pwdForm.resetFields(); }}
        footer={
          newPwdResult ? (
            <Space>
              <Button onClick={copyToClipboard} type="primary">
                {t("user.copy_password")}
              </Button>
              <Button onClick={() => { setPwdModalOpen(false); setNewPwdResult(null); }}>
                {t("common.close")}
              </Button>
            </Space>
          ) : (
            <Space>
              <Button onClick={handleGeneratePwd} loading={resetPwdMut.isPending}>
                {t("user.generate_password")}
              </Button>
              <Button
                type="primary"
                onClick={handlePwdSubmit}
                loading={resetPwdMut.isPending}
              >
                {t("user.set_password")}
              </Button>
              <Button onClick={() => { setPwdModalOpen(false); pwdForm.resetFields(); }}>
                {t("common.cancel")}
              </Button>
            </Space>
          )
        }
        destroyOnClose
      >
        {newPwdResult ? (
          <div style={{ textAlign: "center", padding: "16px 0" }}>
            <Typography.Paragraph>{t("user.new_password_ready")}</Typography.Paragraph>
            <Typography.Text
              code
              copyable
              style={{ fontSize: 18, letterSpacing: 2 }}
            >
              {newPwdResult}
            </Typography.Text>
            <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
              {t("user.password_shown_once")}
            </Typography.Paragraph>
          </div>
        ) : (
          <Form form={pwdForm} layout="vertical" style={{ marginTop: 16 }}>
            <Form.Item
              name="password"
              label={t("user.new_password")}
              rules={[{ min: 6, message: t("user.password_min_length") }]}
            >
              <Input.Password placeholder={t("user.password_or_generate")} />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
}
