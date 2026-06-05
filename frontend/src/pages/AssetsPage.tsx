import { useState } from "react";
import {
  Table, Button, Modal, Form, Input, InputNumber, DatePicker, Space,
  Typography, Popconfirm, message, Image, Upload, Select,
} from "antd";
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, PictureOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import {
  getAssets, createAsset, updateAsset, deleteAsset, uploadAssetImage,
  getAssetImageUrl, type AssetItem,
} from "../api/assets";
import { getCashRegisters } from "../api/cashRegisters";
import { useHasAnyRole } from "../hooks/useRole";

const { Title, Text } = Typography;

const fmt = (v: number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function AssetsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const isAdmin = useHasAnyRole("admin");

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AssetItem | null>(null);
  const [form] = Form.useForm();
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const { data: assets = [], isLoading } = useQuery({
    queryKey: ["assets"],
    queryFn: () => getAssets().then(r => r.data),
  });

  const { data: registers = [] } = useQuery({
    queryKey: ["cash-registers"],
    queryFn: () => getCashRegisters().then(r => r.data),
  });

  const registerOptions = registers.map(r => ({
    value: `${r.name} (${r.currency})`,
    label: `${r.name} (${r.currency})`,
  }));

  const createMut = useMutation({
    mutationFn: async (values: any) => {
      const res = await createAsset({
        name: values.name,
        quantity: values.quantity,
        price: values.price,
        account: values.account || undefined,
        purchase_date: values.purchase_date ? values.purchase_date.format("YYYY-MM-DD") : undefined,
      });
      if (imageFile) {
        await uploadAssetImage(res.data.id, imageFile);
      }
      return res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      setModalOpen(false);
      form.resetFields();
      setImageFile(null);
      setImagePreview(null);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const updateMut = useMutation({
    mutationFn: async ({ id, values }: { id: string; values: any }) => {
      const res = await updateAsset(id, {
        name: values.name,
        quantity: values.quantity,
        price: values.price,
        account: values.account || undefined,
        purchase_date: values.purchase_date ? values.purchase_date.format("YYYY-MM-DD") : undefined,
      });
      if (imageFile) {
        await uploadAssetImage(id, imageFile);
      }
      return res;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      setModalOpen(false);
      setEditing(null);
      form.resetFields();
      setImageFile(null);
      setImagePreview(null);
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteAsset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setImageFile(null);
    setImagePreview(null);
    setModalOpen(true);
  };

  const openEdit = (asset: AssetItem) => {
    setEditing(asset);
    setImageFile(null);
    setImagePreview(null);
    form.setFieldsValue({
      name: asset.name,
      quantity: asset.quantity,
      price: asset.price,
      account: asset.account,
      purchase_date: asset.purchase_date ? dayjs(asset.purchase_date) : undefined,
    });
    setModalOpen(true);
  };

  const handleSubmit = (values: any) => {
    if (editing) {
      updateMut.mutate({ id: editing.id, values });
    } else {
      createMut.mutate(values);
    }
  };

  const handleImageSelect = (file: File) => {
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = e => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);
    return false;
  };

  const grandTotal = assets.reduce((sum, a) => sum + Number(a.total), 0);

  const columns = [
    {
      title: t("asset.name"),
      dataIndex: "name",
      key: "name",
      render: (v: string) => <strong>{v}</strong>,
    },
    {
      title: t("asset.image"),
      key: "image",
      width: 80,
      render: (_: any, row: AssetItem) =>
        row.image_path ? (
          <Image
            src={getAssetImageUrl(row.id)}
            width={52}
            height={52}
            style={{ objectFit: "cover", borderRadius: 4 }}
            placeholder={<PictureOutlined style={{ fontSize: 24, color: "#bfbfbf" }} />}
          />
        ) : (
          <PictureOutlined style={{ fontSize: 24, color: "#d9d9d9" }} />
        ),
    },
    {
      title: t("asset.quantity"),
      dataIndex: "quantity",
      key: "quantity",
      align: "right" as const,
      render: (v: number) => Number(v).toLocaleString("ru-RU"),
    },
    {
      title: t("asset.price"),
      dataIndex: "price",
      key: "price",
      align: "right" as const,
      render: (v: number) => fmt(v),
    },
    {
      title: t("asset.total"),
      dataIndex: "total",
      key: "total",
      align: "right" as const,
      render: (v: number) => <strong>{fmt(v)}</strong>,
    },
    {
      title: t("asset.account"),
      dataIndex: "account",
      key: "account",
      render: (v: string) => v || "—",
    },
    {
      title: t("asset.purchase_date"),
      dataIndex: "purchase_date",
      key: "purchase_date",
      render: (v: string) => v || "—",
    },
    {
      title: t("common.created_by"),
      dataIndex: "created_by_name",
      key: "created_by",
      width: 130,
    },
    ...(isAdmin
      ? [
          {
            title: t("common.actions"),
            key: "actions",
            width: 100,
            render: (_: any, row: AssetItem) => (
              <Space>
                <Button icon={<EditOutlined />} size="small" onClick={() => openEdit(row)} />
                <Popconfirm
                  title={t("asset.delete_confirm")}
                  onConfirm={() => deleteMut.mutate(row.id)}
                  okText={t("common.yes")}
                  cancelText={t("common.cancel")}
                >
                  <Button icon={<DeleteOutlined />} size="small" danger />
                </Popconfirm>
              </Space>
            ),
          },
        ]
      : []),
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t("asset.title")}</Title>
        {isAdmin && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            {t("asset.add_new")}
          </Button>
        )}
      </div>

      <Table
        columns={columns}
        dataSource={assets}
        rowKey="id"
        loading={isLoading}
        size="small"
        scroll={{ x: "max-content" }}
        pagination={false}
        summary={() => (
          <Table.Summary.Row>
            <Table.Summary.Cell index={0} colSpan={4}>
              <Text strong>ИТОГО</Text>
            </Table.Summary.Cell>
            <Table.Summary.Cell index={1} align="right">
              <Text strong style={{ color: "#1677ff" }}>{fmt(grandTotal)}</Text>
            </Table.Summary.Cell>
            <Table.Summary.Cell index={2} colSpan={isAdmin ? 4 : 3} />
          </Table.Summary.Row>
        )}
      />

      <Modal
        open={modalOpen}
        title={editing ? t("asset.edit") : t("asset.add_new")}
        onOk={() => form.validateFields().then(handleSubmit)}
        onCancel={() => {
          setModalOpen(false);
          setEditing(null);
          form.resetFields();
          setImageFile(null);
          setImagePreview(null);
        }}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        confirmLoading={createMut.isPending || updateMut.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t("asset.name")} rules={[{ required: true }]}>
            <Input />
          </Form.Item>

          <Form.Item label={t("asset.image")}>
            <Space direction="vertical" style={{ width: "100%" }}>
              {(imagePreview || editing?.image_path) && (
                <Image
                  src={imagePreview || getAssetImageUrl(editing!.id)}
                  width={100}
                  height={100}
                  style={{ objectFit: "cover", borderRadius: 4 }}
                />
              )}
              <Upload
                accept="image/jpeg,image/png,image/webp"
                showUploadList={false}
                beforeUpload={handleImageSelect}
              >
                <Button icon={<UploadOutlined />} size="small">
                  {editing?.image_path ? t("asset.change_image") : t("asset.upload_image")}
                </Button>
              </Upload>
              {imageFile && <span style={{ fontSize: 12, color: "#52c41a" }}>{imageFile.name}</span>}
            </Space>
          </Form.Item>

          <Form.Item name="quantity" label={t("asset.quantity")} rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} min={0} step={1} precision={3} />
          </Form.Item>

          <Form.Item name="price" label={t("asset.price")} rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} min={0} step={0.01} precision={2} />
          </Form.Item>

          <Form.Item name="account" label={t("asset.account")}>
            <Select
              allowClear
              showSearch
              placeholder="Выберите кассу"
              options={registerOptions}
              filterOption={(input, opt) =>
                (opt?.label ?? "").toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>

          <Form.Item name="purchase_date" label={t("asset.purchase_date")}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
