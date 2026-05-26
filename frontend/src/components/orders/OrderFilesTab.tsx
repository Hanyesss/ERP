import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Button, Col, Image, Popconfirm, Row, Select, Spin, Typography, Upload, message,
} from "antd";
import {
  DeleteOutlined, FilePdfOutlined, FileOutlined, UploadOutlined,
} from "@ant-design/icons";
import { getOrderFiles, uploadOrderFile, deleteOrderFile, getFileUrl } from "../../api/orders";
import type { OrderFile } from "../../types/order";

const { Text } = Typography;

const FILE_TYPES = [
  { value: "invoice", labelKey: "order.file_type_invoice" },
  { value: "packing", labelKey: "order.file_type_packing" },
  { value: "cargo_photo", labelKey: "order.file_type_cargo_photo" },
  { value: "other", labelKey: "order.file_type_other" },
];

interface Props {
  orderId: string;
}

export default function OrderFilesTab({ orderId }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingFileType, setPendingFileType] = useState("cargo_photo");
  const [uploading, setUploading] = useState(false);

  const { data: files, isLoading } = useQuery({
    queryKey: ["order-files", orderId],
    queryFn: () => getOrderFiles(orderId).then(r => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (fileId: string) => deleteOrderFile(orderId, fileId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["order-files", orderId] });
      message.success(t("common.delete") + " ✓");
    },
  });

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadOrderFile(orderId, file, pendingFileType);
      qc.invalidateQueries({ queryKey: ["order-files", orderId] });
      message.success(t("order.upload_file") + " ✓");
    } catch (err: any) {
      const detail = err.response?.data?.detail || "Error";
      if (detail.includes("too large")) {
        message.error(t("validation.file_too_large"));
      } else if (detail.includes("not allowed")) {
        message.error(t("validation.file_type_not_allowed"));
      } else {
        message.error(detail);
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  if (isLoading) return <Spin />;

  return (
    <div>
      {/* Upload toolbar */}
      <Row gutter={8} align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Select
            value={pendingFileType}
            onChange={setPendingFileType}
            style={{ width: 180 }}
            options={FILE_TYPES.map(ft => ({ value: ft.value, label: t(ft.labelKey) }))}
          />
        </Col>
        <Col>
          <Button
            icon={<UploadOutlined />}
            loading={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {t("order.upload_file")}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
        </Col>
        <Col>
          <Text type="secondary" style={{ fontSize: 12 }}>
            JPEG, PNG, WebP, PDF — max 10 MB
          </Text>
        </Col>
      </Row>

      {/* File grid */}
      {(!files || files.length === 0) ? (
        <Text type="secondary">{t("order.no_files")}</Text>
      ) : (
        <Row gutter={[12, 12]}>
          {files.map(file => (
            <FileCard
              key={file.id}
              file={file}
              onDelete={() => deleteMutation.mutate(file.id)}
              t={t}
            />
          ))}
        </Row>
      )}
    </div>
  );
}

function FileCard({ file, onDelete, t }: { file: OrderFile; onDelete: () => void; t: (k: string) => string }) {
  const isImage = file.mime_type?.startsWith("image/");
  const isPdf = file.mime_type === "application/pdf";
  const url = getFileUrl(file.file_url);

  return (
    <Col>
      <div
        style={{
          width: 120, border: "1px solid #f0f0f0", borderRadius: 8, padding: 8,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
        }}
      >
        {isImage ? (
          <Image
            src={url}
            width={100}
            height={80}
            style={{ objectFit: "cover", borderRadius: 4 }}
            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            preview={{ src: url }}
          />
        ) : isPdf ? (
          <a href={url} target="_blank" rel="noreferrer">
            <FilePdfOutlined style={{ fontSize: 48, color: "#ff4d4f" }} />
          </a>
        ) : (
          <a href={url} target="_blank" rel="noreferrer">
            <FileOutlined style={{ fontSize: 48, color: "#8c8c8c" }} />
          </a>
        )}

        <Text ellipsis style={{ fontSize: 11, maxWidth: 104, textAlign: "center" }} title={file.file_name}>
          {file.file_name}
        </Text>
        <Text type="secondary" style={{ fontSize: 10 }}>
          {FILE_TYPES.find(ft => ft.value === file.file_type)
            ? t(`order.file_type_${file.file_type}`)
            : file.file_type}
        </Text>
        {file.file_size_bytes && (
          <Text type="secondary" style={{ fontSize: 10 }}>
            {(file.file_size_bytes / 1024).toFixed(0)} KB
          </Text>
        )}

        <Popconfirm
          title={t("order.delete_file_confirm")}
          onConfirm={onDelete}
          okText={t("common.yes")}
          cancelText={t("common.no")}
        >
          <Button size="small" danger icon={<DeleteOutlined />} style={{ width: "100%" }} />
        </Popconfirm>
      </div>
    </Col>
  );
}
