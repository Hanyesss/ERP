import { useState } from "react";
import {
  Button, Table, Typography, Space, Modal, Form, Input,
  Switch, message, Popconfirm, Row, Col,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import {
  getWarehouses, createWarehouse, updateWarehouse, deleteWarehouse,
  type Warehouse,
} from "../api/warehouses";

const { Title } = Typography;

export default function WarehousesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingWarehouse, setEditingWarehouse] = useState<Warehouse | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => getWarehouses().then(r => r.data),
  });

  const createMutation = useMutation({
    mutationFn: createWarehouse,
    onSuccess: () => {
      message.success("✓");
      qc.invalidateQueries({ queryKey: ["warehouses"] });
      setModalOpen(false);
      form.resetFields();
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateWarehouse(id, data),
    onSuccess: () => {
      message.success("✓");
      qc.invalidateQueries({ queryKey: ["warehouses"] });
      setModalOpen(false);
      form.resetFields();
      setEditingWarehouse(null);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWarehouse,
    onSuccess: () => {
      message.success("✓");
      qc.invalidateQueries({ queryKey: ["warehouses"] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const openCreate = () => {
    setEditingWarehouse(null);
    form.resetFields();
    form.setFieldsValue({ is_active: true });
    setModalOpen(true);
  };

  const openEdit = (wh: Warehouse) => {
    setEditingWarehouse(wh);
    form.setFieldsValue({ name: wh.name, name_cn: wh.name_cn, city: wh.city, is_active: wh.is_active });
    setModalOpen(true);
  };

  const handleSubmit = (values: any) => {
    if (editingWarehouse) {
      updateMutation.mutate({ id: editingWarehouse.id, data: values });
    } else {
      createMutation.mutate(values);
    }
  };

  const columns: ColumnsType<Warehouse> = [
    {
      title: t("warehouse.name"),
      dataIndex: "name",
      key: "name",
    },
    {
      title: t("warehouse.name_cn"),
      dataIndex: "name_cn",
      key: "name_cn",
    },
    {
      title: t("warehouse.city"),
      dataIndex: "city",
      key: "city",
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 120,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            {t("warehouse.edit")}
          </Button>
          <Popconfirm
            title="Удалить склад?"
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText={t("common.yes")}
            cancelText={t("common.cancel")}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("warehouse.title")}</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            {t("warehouse.add_new")}
          </Button>
        </Col>
      </Row>

      <Table
        dataSource={data || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={false}
        size="middle"
      />

      <Modal
        open={modalOpen}
        title={editingWarehouse ? t("warehouse.edit") : t("warehouse.add_new")}
        onCancel={() => { setModalOpen(false); form.resetFields(); setEditingWarehouse(null); }}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label={t("warehouse.name")} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name_cn" label={t("warehouse.name_cn")}>
            <Input />
          </Form.Item>
          <Form.Item name="city" label={t("warehouse.city")}>
            <Input />
          </Form.Item>
          <Form.Item name="is_active" label={t("warehouse.is_active")} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
