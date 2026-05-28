import { useRef, useState } from "react";
import { Button, Image, Popconfirm, Tooltip, message, Spin } from "antd";
import { PlusOutlined, DeleteOutlined, CameraOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { uploadItemPhoto, deleteItemPhoto, getItemPhotoUrl } from "../../api/orders";

interface Props {
  itemId: string;
  disabled?: boolean;
  disabledHint?: string;
}

export default function ItemPhotosEditor({ itemId, disabled, disabledHint }: Props) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewSrc, setPreviewSrc] = useState("");

  const { data: photos = [], isLoading } = useQuery({
    queryKey: ["item-photos", itemId],
    queryFn: async () => {
      const res = await import("../../api/orders").then(m => m.getItemPhotos(itemId));
      return res.data as any[];
    },
    enabled: !disabled,
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadItemPhoto(itemId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["item-photos", itemId] });
      qc.invalidateQueries({ queryKey: ["order"] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Upload failed"),
  });

  const deleteMut = useMutation({
    mutationFn: (photoId: string) => deleteItemPhoto(itemId, photoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["item-photos", itemId] });
      qc.invalidateQueries({ queryKey: ["order"] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Delete failed"),
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    uploadMut.mutate(file);
    e.target.value = "";
  };

  if (disabled) {
    return (
      <Tooltip title={disabledHint}>
        <Button size="small" icon={<CameraOutlined />} disabled>
          Фото
        </Button>
      </Tooltip>
    );
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
      {isLoading && <Spin size="small" />}

      {photos.map((ph: any) => (
        <div key={ph.id} style={{ position: "relative" }}>
          <img
            src={getItemPhotoUrl(itemId, ph.id)}
            alt={ph.file_name}
            style={{ width: 52, height: 52, objectFit: "cover", borderRadius: 4, border: "1px solid #d9d9d9", cursor: "pointer" }}
            onClick={() => { setPreviewSrc(getItemPhotoUrl(itemId, ph.id)); setPreviewOpen(true); }}
          />
          <Popconfirm
            title="Удалить фото?"
            onConfirm={() => deleteMut.mutate(ph.id)}
            okText="Да"
            cancelText="Нет"
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              style={{ position: "absolute", top: -6, right: -6, width: 18, height: 18, padding: 0, fontSize: 10, minWidth: 0 }}
              loading={deleteMut.isPending}
            />
          </Popconfirm>
        </div>
      ))}

      <Tooltip title="Загрузить фото (JPEG/PNG/WebP)">
        <Button
          size="small"
          icon={<PlusOutlined />}
          loading={uploadMut.isPending}
          onClick={() => inputRef.current?.click()}
          style={{ width: 52, height: 52, borderStyle: "dashed" }}
        />
      </Tooltip>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      <Image
        style={{ display: "none" }}
        preview={{
          visible: previewOpen,
          src: previewSrc,
          onVisibleChange: setPreviewOpen,
        }}
      />
    </div>
  );
}
