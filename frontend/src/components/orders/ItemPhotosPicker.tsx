/**
 * Local-only photo picker for order item rows.
 * Stores File objects in memory — no upload happens here.
 * Used in the create/edit form. After order save, the parent
 * calls uploadPendingPhotos() with the actual item IDs.
 */
import { useRef } from "react";
import { Button, Image, Popconfirm, Tooltip } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";

interface LocalPhoto {
  localId: string;
  file: File;
  previewUrl: string;
}

interface Props {
  photos: LocalPhoto[];
  onChange: (photos: LocalPhoto[]) => void;
}

export type { LocalPhoto };

export default function ItemPhotosPicker({ photos, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleAdd = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const newPhotos: LocalPhoto[] = files.map(f => ({
      localId: `${Date.now()}-${Math.random()}`,
      file: f,
      previewUrl: URL.createObjectURL(f),
    }));
    onChange([...photos, ...newPhotos]);
    e.target.value = "";
  };

  const handleRemove = (localId: string) => {
    const removed = photos.find(p => p.localId === localId);
    if (removed) URL.revokeObjectURL(removed.previewUrl);
    onChange(photos.filter(p => p.localId !== localId));
  };

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
      <Image.PreviewGroup>
        {photos.map(ph => (
          <div key={ph.localId} style={{ position: "relative" }}>
            <Image
              src={ph.previewUrl}
              width={48}
              height={48}
              style={{ objectFit: "cover", borderRadius: 4, border: "1px solid #d9d9d9" }}
              preview={{ src: ph.previewUrl }}
            />
            <Popconfirm title="Удалить?" onConfirm={() => handleRemove(ph.localId)} okText="Да" cancelText="Нет">
              <Button
                size="small" danger icon={<DeleteOutlined />}
                style={{ position: "absolute", top: -6, right: -6, width: 18, height: 18, padding: 0, fontSize: 10, minWidth: 0 }}
              />
            </Popconfirm>
          </div>
        ))}
      </Image.PreviewGroup>

      <Tooltip title="Добавить фото (JPEG/PNG/WebP)">
        <Button
          size="small" icon={<PlusOutlined />}
          onClick={() => inputRef.current?.click()}
          style={{ width: 48, height: 48, borderStyle: "dashed" }}
        />
      </Tooltip>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        style={{ display: "none" }}
        onChange={handleAdd}
      />
    </div>
  );
}
