import { useState, useEffect, useRef, useCallback } from "react";
import {
  Button, Table, Typography, Space, Modal, Form, Input, InputNumber,
  Switch, message, Popconfirm, Row, Col, Select, Tabs, Collapse,
  Upload, Image, Tag, Badge, Spin, Checkbox, Divider, Empty,
} from "antd";
import {
  PlusOutlined, EditOutlined, DeleteOutlined, QrcodeOutlined,
  UploadOutlined, InboxOutlined, SendOutlined, FilePdfOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import {
  getWarehouses, createWarehouse, updateWarehouse, deleteWarehouse,
  type Warehouse,
} from "../api/warehouses";
import {
  getBalance, createBox, updateBox, deleteBox, uploadBoxPhoto, uploadBoxItemPhoto,
  getQrLabelUrl, generatePackingListPreview, generateQrBulkPdf, shipBoxes,
  getShipped, getPackingLists,
  type ClientGroup, type WarehouseBox, type BoxCreate, type BoxItemIn,
  type BoxItemData, type PackingListRecord,
} from "../api/warehouseBoxes";
import apiClient from "../api/client";
import { getCounterparties } from "../api/counterparties";
import type { User } from "../types";

const { Title, Text } = Typography;
const { TabPane } = Tabs;
const { Panel } = Collapse;
const { Option } = Select;

interface Props {
  user?: User;
}

// ── Util ──────────────────────────────────────────────────────────────────────

function fmtNum(v: number | null | undefined, decimals = 3): string {
  if (v == null) return "—";
  return v.toFixed(decimals).replace(/\.?0+$/, "");
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── QR Scanner Modal ──────────────────────────────────────────────────────────

function QrScanModal({
  open,
  onShip,
  onClose,
}: {
  open: boolean;
  onShip: (codes: string[]) => Promise<void>;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [scanned, setScanned] = useState<string[]>([]);
  const [manualCode, setManualCode] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [shipping, setShipping] = useState(false);
  const scannerRef = useRef<any>(null);
  const scannerDivId = "qr-scanner-stream";

  const addCode = useCallback((code: string) => {
    const c = code.trim().toUpperCase();
    if (!c) return;

    // Останавливаем камеру в любом случае
    if (scannerRef.current) {
      scannerRef.current.stop().catch(() => {});
      scannerRef.current = null;
    }
    setStreaming(false);

    setScanned((prev) => {
      if (prev.includes(c)) {
        message.warning({ content: `${c}: ${t("warehouse.scan_already_added")}`, duration: 3 });
        return prev;
      }
      return [...prev, c];
    });
  }, [t]);

  const stopStream = async () => {
    if (scannerRef.current) {
      await scannerRef.current.stop().catch(() => {});
      scannerRef.current = null;
    }
    setStreaming(false);
  };

  const startStream = async () => {
    setStreaming(true);
    try {
      const { Html5Qrcode, Html5QrcodeSupportedFormats } = await import("html5-qrcode");
      // Поддерживаем и QR коды, и штрихкоды (1D)
      const scanner = new Html5Qrcode(scannerDivId, {
        formatsToSupport: [
          Html5QrcodeSupportedFormats.QR_CODE,
          Html5QrcodeSupportedFormats.CODE_128,
          Html5QrcodeSupportedFormats.CODE_39,
          Html5QrcodeSupportedFormats.EAN_13,
          Html5QrcodeSupportedFormats.EAN_8,
          Html5QrcodeSupportedFormats.DATA_MATRIX,
          Html5QrcodeSupportedFormats.PDF_417,
        ],
        verbose: false,
      } as any);
      scannerRef.current = scanner;
      await scanner.start(
        { facingMode: "environment" },
        { fps: 15, qrbox: { width: 250, height: 250 } },
        (text: string) => addCode(text),
        () => {}
      );
    } catch (e: any) {
      setStreaming(false);
      message.error("Камера недоступна. Используйте HTTPS-адрес сайта.");
      if (scannerRef.current) { scannerRef.current.clear().catch(() => {}); scannerRef.current = null; }
    }
  };

  useEffect(() => {
    if (!open) { stopStream(); setScanned([]); setManualCode(""); }
  }, [open]);

  const handleShip = async () => {
    if (!scanned.length) { message.warning(t("warehouse.no_boxes_selected")); return; }
    setShipping(true);
    try { await onShip(scanned); onClose(); }
    finally { setShipping(false); }
  };

  return (
    <Modal
      open={open}
      title={t("warehouse.shipment_title")}
      onCancel={() => { stopStream(); onClose(); }}
      footer={null}
      width={460}
      style={{ maxWidth: "100vw" }}
      destroyOnClose
    >
      {/* Область стрима */}
      <div
        id={scannerDivId}
        style={{
          width: "100%",
          minHeight: streaming ? 300 : 0,
          background: "#000",
          borderRadius: 8,
          overflow: "hidden",
          marginBottom: streaming ? 12 : 0,
        }}
      />

      {/* Кнопка сканирования — снова после добавления кода */}
      {!streaming && (
        <Button
          type="primary"
          icon={<QrcodeOutlined />}
          size="large"
          block
          onClick={startStream}
          style={{ marginBottom: 12, height: 52, fontSize: 16 }}
        >
          {t("warehouse.scan_qr")}
        </Button>
      )}

      {/* Ручной ввод */}
      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col flex="auto">
          <Input
            placeholder={t("warehouse.box_code_placeholder")}
            value={manualCode}
            onChange={(e) => setManualCode(e.target.value.toUpperCase())}
            onPressEnter={() => { addCode(manualCode); setManualCode(""); }}
          />
        </Col>
        <Col>
          <Button onClick={() => { const v = manualCode; setManualCode(""); addCode(v); }}>
            {t("warehouse.add_manually")}
          </Button>
        </Col>
      </Row>

      {/* Отсканированные коды */}
      {scanned.length > 0 && (
        <div style={{ marginBottom: 12, padding: "8px 12px", background: "#f6ffed", borderRadius: 6, border: "1px solid #b7eb8f" }}>
          <Text strong style={{ fontSize: 13 }}>{t("warehouse.scanned_count")}: {scanned.length}</Text>
          <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
            {scanned.map((c) => (
              <Tag key={c} closable onClose={() => setScanned((p) => p.filter((x) => x !== c))} color="green">{c}</Tag>
            ))}
          </div>
        </div>
      )}

      <Button
        type="primary" danger icon={<SendOutlined />} size="large" block
        loading={shipping} disabled={!scanned.length} onClick={handleShip}
      >
        {t("warehouse.do_ship")} ({scanned.length})
      </Button>
    </Modal>
  );
}

// ── Receipt Modal ─────────────────────────────────────────────────────────────

interface ItemRow { name: string; qty: number; tracking: string; files: File[]; previews: string[]; }

// Сжатие изображения на фронте перед загрузкой
async function compressImage(file: File, maxPx = 800, quality = 0.72): Promise<Blob> {
  return new Promise(resolve => {
    const img = new window.Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(1, maxPx / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(b => resolve(b || file), "image/jpeg", quality);
    };
    img.onerror = () => resolve(file);
    img.src = url;
  });
}

function ReceiptModal({
  open, warehouses, onSuccess, onClose, defaultClientId,
}: {
  open: boolean; warehouses: Warehouse[];
  onSuccess: (boxes: WarehouseBox[]) => void;
  onClose: () => void;
  defaultClientId?: string;
}) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [creating, setCreating] = useState(false);
  const [createdBoxes, setCreatedBoxes] = useState<WarehouseBox[]>([]);
  // Главное фото коробки
  const [mainPhotoFile, setMainPhotoFile] = useState<File | null>(null);
  const [mainPhotoPreview, setMainPhotoPreview] = useState<string | null>(null);
  // Камера для сканирования трек-номера
  const [trackingScanOpen, setTrackingScanOpen] = useState(false);
  const trackingScannerRef = useRef<any>(null);
  const trackingDivId = "tracking-qr-scanner";
  // Динамический список позиций товаров
  const [items, setItems] = useState<ItemRow[]>([{ name: "", qty: 1, tracking: "", files: [], previews: [] }]);

  const { data: counterparties = [] } = useQuery({
    queryKey: ["counterparties-select"],
    queryFn: () => getCounterparties({ page_size: 500 }).then((r) => r.data.items),
  });
  const clients = counterparties.filter((c: any) => c.type === "client" || c.type === "both");

  // Предзаполняем клиента из предыдущего сеанса
  useEffect(() => {
    if (open && defaultClientId) {
      form.setFieldValue("counterparty_id", defaultClientId);
    }
  }, [open, defaultClientId, form]);

  const setItemField = (idx: number, field: keyof ItemRow, value: any) =>
    setItems(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));

  const handleItemPhoto = (idx: number, file: File) => {
    const item = items[idx];
    if (item.files.length >= 3) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      setItems(prev => prev.map((r, i) =>
        i === idx ? { ...r, files: [...r.files, file], previews: [...r.previews, reader.result as string] } : r
      ));
    };
    reader.readAsDataURL(file);
  };

  const removeItemPhoto = (idx: number, photoIdx: number) => {
    setItems(prev => prev.map((r, i) =>
      i === idx
        ? { ...r, files: r.files.filter((_, j) => j !== photoIdx), previews: r.previews.filter((_, j) => j !== photoIdx) }
        : r
    ));
  };

  const addItem = () => setItems(prev => [...prev, { name: "", qty: 1, tracking: "", files: [], previews: [] }]);
  const removeItem = (idx: number) => setItems(prev => prev.filter((_, i) => i !== idx));

  const handleSubmit = async (values: any) => {
    const validItems = items.filter(i => i.name.trim());

    setCreating(true);
    try {
      const mainName = values.item_name_label || validItems[0].name;
      const payload: BoxCreate = {
        counterparty_id: values.counterparty_id,
        warehouse_id: values.warehouse_id,
        weight: values.weight,
        volume: values.volume,
        item_name: mainName,
        description: values.description,
        tracking_number: values.tracking_number || undefined,
        count: values.box_count || 1,
        items: validItems.map((it, idx) => ({
          name: it.name, quantity: it.qty,
          tracking_code: it.tracking || undefined,
          sort_order: idx,
        })),
      };

      const res = await createBox(payload);
      const rawBoxes = Array.isArray(res.data) ? res.data : [res.data];

      const firstBox = rawBoxes[0];
      // Загружаем главное фото коробки (сжимаем перед загрузкой)
      if (firstBox && mainPhotoFile) {
        try {
          const compressed = await compressImage(mainPhotoFile, 800, 0.72);
          const f = new File([compressed], "box_photo.jpg", { type: "image/jpeg" });
          await uploadBoxPhoto(firstBox.id, f);
        } catch {}
      }
      // Загружаем фото позиций для первой коробки (до 3 на позицию)
      if (firstBox && firstBox.items) {
        for (let idx = 0; idx < validItems.length; idx++) {
          const files = validItems[idx].files;
          const savedItem = firstBox.items[idx];
          if (savedItem && files.length > 0) {
            for (const f of files) {
              try {
                const compressed = await compressImage(f, 800, 0.72);
                const cf = new File([compressed], "item_photo.jpg", { type: "image/jpeg" });
                await uploadBoxItemPhoto(firstBox.id, savedItem.id, cf);
              } catch {}
            }
          }
        }
      }

      setCreatedBoxes(rawBoxes);
      onSuccess(rawBoxes);
    } catch (e: any) {
      message.error(e.response?.data?.detail || "Ошибка создания");
    } finally {
      setCreating(false);
    }
  };

  const handleClose = () => {
    form.resetFields();
    setItems([{ name: "", qty: 1, tracking: "", files: [], previews: [] }]);
    setCreatedBoxes([]);
    setMainPhotoFile(null); setMainPhotoPreview(null);
    onClose();
  };

  const handleAddMore = () => {
    form.setFieldValue("box_count", 1);
    setItems([{ name: "", qty: 1, tracking: "", files: [], previews: [] }]);
    setMainPhotoFile(null); setMainPhotoPreview(null);
    setCreatedBoxes([]);
    // Оставляем клиента и склад
  };

  const openQrLabel = async (box: WarehouseBox) => {
    try {
      const res = await apiClient.get(getQrLabelUrl(box.id), { responseType: "blob" });
      downloadBlob(res.data as Blob, `${box.box_code}.pdf`);
    } catch { message.error("Ошибка генерации наклейки"); }
  };

  return (
    <Modal open={open} title={t("warehouse.receipt_title")} onCancel={handleClose}
      footer={null} width={580} style={{ maxWidth: "100vw" }} destroyOnClose>

      {createdBoxes.length === 0 ? (
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          {/* Клиент + Склад */}
          <Row gutter={12}>
            <Col span={14}>
              <Form.Item name="counterparty_id" label={t("warehouse.client")} rules={[{ required: true }]}>
                <Select showSearch placeholder={t("warehouse.select_client")} optionFilterProp="label"
                  options={clients.map((c: any) => ({
                    value: c.id, label: `${c.code ? `[${c.code}] ` : ""}${c.name}`
                  }))} />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name="warehouse_id" label={t("warehouse.select_warehouse")} rules={[{ required: true }]}>
                <Select placeholder={t("warehouse.select_warehouse")}
                  options={warehouses.map(w => ({ value: w.id, label: w.name + (w.city ? ` (${w.city})` : "") }))} />
              </Form.Item>
            </Col>
          </Row>

          {/* Вес / Объём / Количество коробок */}
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="weight" label={t("warehouse.weight")} rules={[{ required: true }]}>
                <InputNumber min={0} step={0.1} precision={3} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="volume" label={t("warehouse.volume")} rules={[{ required: true }]}>
                <InputNumber min={0} step={0.001} precision={4} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="box_count" label={t("warehouse.box_count")} initialValue={1}>
                <InputNumber min={1} max={500} precision={0} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          {/* Наименование коробки (общее) */}
          <Form.Item name="item_name_label" label={t("warehouse.item_name")} rules={[{ required: true }]}>
            <Input placeholder={t("warehouse.item_name_label")} />
          </Form.Item>

          <Form.Item name="description" label={t("warehouse.description")}>
            <Input.TextArea rows={1} />
          </Form.Item>


          {/* Задача 2: главное фото коробки */}
          <Form.Item label={t("warehouse.photo_optional")}>
            <Space align="start">
              <Upload accept="image/jpeg,image/png,image/webp" showUploadList={false}
                beforeUpload={f => {
                  const reader = new FileReader();
                  reader.onloadend = () => setMainPhotoPreview(reader.result as string);
                  reader.readAsDataURL(f);
                  setMainPhotoFile(f);
                  return false;
                }}>
                <Button icon={<UploadOutlined />} style={{ background: mainPhotoPreview ? "#f6ffed" : undefined }}>
                  {mainPhotoPreview ? "✓ " + t("warehouse.photo") : t("warehouse.upload_photo")}
                </Button>
              </Upload>
              {mainPhotoPreview && (
                <Image src={mainPhotoPreview} width={48} height={48}
                  style={{ objectFit: "cover", borderRadius: 4, cursor: "pointer" }} />
              )}
              {mainPhotoPreview && (
                <Button size="small" type="text" danger
                  onClick={() => { setMainPhotoFile(null); setMainPhotoPreview(null); }}>✕</Button>
              )}
            </Space>
          </Form.Item>

          {/* Позиции товаров — с отступом вправо */}
          <Divider style={{ margin: "8px 0" }}>{t("warehouse.box_items_section")}</Divider>
          <div style={{ paddingLeft: 16, borderLeft: "3px solid #f0f0f0" }}>
            {items.map((item, idx) => {
              const scanDivId = `item-scan-${idx}`;
              return (
                <div key={idx} style={{ marginBottom: 8, background: "#fafafa", borderRadius: 6, padding: "8px 10px" }}>
                  {/* Строка 1: название + количество */}
                  <Row gutter={8} align="middle" style={{ marginBottom: 4 }}>
                    <Col flex="auto">
                      <Input
                        placeholder={t("warehouse.item_row_name")}
                        value={item.name}
                        onChange={e => setItemField(idx, "name", e.target.value)}
                      />
                    </Col>
                    <Col style={{ width: 72 }}>
                      <InputNumber
                        min={1} precision={0} placeholder={t("warehouse.item_row_qty")}
                        value={item.qty}
                        onChange={v => setItemField(idx, "qty", v ?? 1)}
                        style={{ width: "100%" }}
                      />
                    </Col>
                    {items.length > 1 && (
                      <Col>
                        <Button size="small" danger icon={<DeleteOutlined />}
                          onClick={() => removeItem(idx)} />
                      </Col>
                    )}
                  </Row>
                  {/* Строка 2: код отслеживания со сканером + фото */}
                  <Row gutter={8} align="middle">
                    <Col flex="auto">
                      <Input
                        size="small"
                        placeholder={t("warehouse.tracking_code_placeholder")}
                        value={item.tracking}
                        onChange={e => setItemField(idx, "tracking", e.target.value)}
                        addonAfter={
                          <Button size="small" type="text" icon={<QrcodeOutlined />}
                            title={t("warehouse.item_scan_tracking")}
                            onClick={async () => {
                              setTrackingScanOpen(true);
                              setTimeout(async () => {
                                try {
                                  const { Html5Qrcode, Html5QrcodeSupportedFormats } = await import("html5-qrcode");
                                  if (trackingScannerRef.current) {
                                    await trackingScannerRef.current.stop().catch(() => {});
                                  }
                                  const scanner = new Html5Qrcode(trackingDivId, {
                                    formatsToSupport: [
                                      Html5QrcodeSupportedFormats.QR_CODE,
                                      Html5QrcodeSupportedFormats.CODE_128,
                                      Html5QrcodeSupportedFormats.CODE_39,
                                      Html5QrcodeSupportedFormats.EAN_13,
                                      Html5QrcodeSupportedFormats.EAN_8,
                                      Html5QrcodeSupportedFormats.DATA_MATRIX,
                                    ],
                                    verbose: false,
                                  } as any);
                                  trackingScannerRef.current = scanner;
                                  await scanner.start(
                                    { facingMode: "environment" },
                                    { fps: 15, qrbox: { width: 300, height: 100 } },
                                    (text: string) => {
                                      setItemField(idx, "tracking", text.trim());
                                      scanner.stop().catch(() => {});
                                      trackingScannerRef.current = null;
                                      setTrackingScanOpen(false);
                                    },
                                    () => {}
                                  );
                                } catch { setTrackingScanOpen(false); }
                              }, 100);
                            }}
                          />
                        }
                      />
                    </Col>
                    {item.previews.map((prev, pi) => (
                      <Col key={pi} style={{ position: "relative" }}>
                        <Image src={prev} width={32} height={32}
                          style={{ objectFit: "cover", borderRadius: 3 }} />
                        <Button
                          size="small" type="text" danger
                          style={{ position: "absolute", top: -6, right: -6, padding: 0, width: 16, height: 16, fontSize: 10, lineHeight: "14px", minWidth: 0 }}
                          onClick={() => removeItemPhoto(idx, pi)}
                        >✕</Button>
                      </Col>
                    ))}
                    {item.files.length < 3 && (
                      <Col>
                        <Upload accept="image/jpeg,image/png,image/webp" showUploadList={false}
                          beforeUpload={f => { handleItemPhoto(idx, f); return false; }}>
                          <Button size="small" icon={<UploadOutlined />}>
                            {item.files.length === 0 ? t("warehouse.item_row_photo") : "+"}
                          </Button>
                        </Upload>
                      </Col>
                    )}
                  </Row>
                  {/* Камера для скана (общая для всех позиций) */}
                  {trackingScanOpen && (
                    <div style={{ marginTop: 6 }}>
                      <div id={trackingDivId} style={{ width: "100%", borderRadius: 8, overflow: "hidden", background: "#000", minHeight: 160 }} />
                      <Button size="small" danger style={{ marginTop: 4 }} onClick={async () => {
                        if (trackingScannerRef.current) {
                          await trackingScannerRef.current.stop().catch(() => {});
                          trackingScannerRef.current = null;
                        }
                        setTrackingScanOpen(false);
                      }}>{t("common.close")}</Button>
                    </div>
                  )}
                </div>
              );
            })}
            <Button type="dashed" icon={<PlusOutlined />} size="small" onClick={addItem}
              style={{ marginTop: 4 }}>
              {t("warehouse.add_item")}
            </Button>
          </div>

          <Row justify="end" gutter={8} style={{ marginTop: 16 }}>
            <Col><Button onClick={handleClose}>{t("common.cancel")}</Button></Col>
            <Col>
              <Button type="primary" htmlType="submit" loading={creating} icon={<InboxOutlined />}>
                {t("warehouse.receipt")}
              </Button>
            </Col>
          </Row>
        </Form>
      ) : (
        <div style={{ textAlign: "center", padding: "16px 0" }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
          {createdBoxes.length === 1 ? (
            <>
              <Title level={5}>{createdBoxes[0].box_code}</Title>
              <Text type="secondary">{createdBoxes[0].item_name}</Text>
              <div style={{ margin: "12px 0" }}>
                <Space>
                  <Tag color="green">{fmtNum(createdBoxes[0].weight)} кг</Tag>
                  <Tag color="blue">{fmtNum(createdBoxes[0].volume, 4)} м³</Tag>
                </Space>
              </div>
            </>
          ) : (
            <>
              <Title level={5}>{t("warehouse.created_boxes_count", { count: createdBoxes.length })}</Title>
              <Text type="secondary">{createdBoxes[0].box_code} … {createdBoxes[createdBoxes.length - 1].box_code}</Text>
            </>
          )}
          <div style={{ margin: "16px 0" }}>
            <Space wrap>
              {createdBoxes.slice(0, 3).map(b => (
                <Button key={b.id} icon={<QrcodeOutlined />} size="small" onClick={() => openQrLabel(b)}>
                  {b.box_code}
                </Button>
              ))}
              {createdBoxes.length > 3 && <Text type="secondary">{t("warehouse.more_boxes", { count: createdBoxes.length - 3 })}</Text>}
            </Space>
          </div>
          <Space>
            <Button onClick={handleAddMore} icon={<PlusOutlined />}>{t("warehouse.add_one_more_box")}</Button>
            <Button onClick={handleClose}>{t("common.close")}</Button>
          </Space>
        </div>
      )}
    </Modal>
  );
}

// ── Edit Box Modal ────────────────────────────────────────────────────────────

function EditBoxModal({
  box,
  onClose,
  onSaved,
}: {
  box: WarehouseBox | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [form] = Form.useForm();

  useEffect(() => {
    if (box) {
      form.setFieldsValue({
        item_name: box.item_name,
        weight: box.weight,
        volume: box.volume,
        description: box.description,
      });
    }
  }, [box, form]);

  const handleSubmit = async (values: any) => {
    if (!box) return;
    try {
      await updateBox(box.id, values);
      message.success("✓");
      onSaved();
      onClose();
    } catch (e: any) {
      message.error(e.response?.data?.detail || "Ошибка");
    }
  };

  return (
    <Modal
      open={!!box}
      title={t("warehouse.edit_box")}
      onCancel={onClose}
      onOk={() => form.submit()}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item name="item_name" label={t("warehouse.item_name")} rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="weight" label={t("warehouse.weight")} rules={[{ required: true }]}>
              <InputNumber min={0} step={0.1} precision={3} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="volume" label={t("warehouse.volume")} rules={[{ required: true }]}>
              <InputNumber min={0} step={0.001} precision={4} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="description" label={t("warehouse.description")}>
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ── Balance Tab ───────────────────────────────────────────────────────────────

function BalanceTab({ warehouses }: { warehouses: Warehouse[] }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [selectedWarehouseId, setSelectedWarehouseId] = useState<string | undefined>();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedBoxIds, setSelectedBoxIds] = useState<Set<string>>(new Set());
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [lastClientId, setLastClientId] = useState<string | undefined>(); // задача 4: запоминаем клиента
  const [shipOpen, setShipOpen] = useState(false);
  const [editBox, setEditBox] = useState<WarehouseBox | null>(null);
  const [expandedClients, setExpandedClients] = useState<string[]>([]);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  const { data: balance = [], isLoading } = useQuery({
    queryKey: ["warehouse-balance", selectedWarehouseId, debouncedSearch],
    queryFn: () =>
      getBalance({
        warehouse_id: selectedWarehouseId,
        search: debouncedSearch || undefined,
      }).then((r) => r.data),
  });

  const deleteMut = useMutation({
    mutationFn: deleteBox,
    onSuccess: () => {
      message.success("✓");
      qc.invalidateQueries({ queryKey: ["warehouse-balance"] });
    },
    onError: (e: any) => message.error(e.response?.data?.detail || "Ошибка"),
  });

  // Selection helpers
  const allBoxIds = balance.flatMap((g) => g.boxes.map((b) => b.id));
  const isBoxSelected = (id: string) => selectedBoxIds.has(id);
  const toggleBox = (id: string) => {
    setSelectedBoxIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleGroup = (group: ClientGroup) => {
    const groupIds = group.boxes.map((b) => b.id);
    const allSelected = groupIds.every((id) => selectedBoxIds.has(id));
    setSelectedBoxIds((prev) => {
      const next = new Set(prev);
      if (allSelected) groupIds.forEach((id) => next.delete(id));
      else groupIds.forEach((id) => next.add(id));
      return next;
    });
  };

  // Selection summary
  const selectedBoxes = balance.flatMap((g) => g.boxes).filter((b) => selectedBoxIds.has(b.id));
  const selWeight = selectedBoxes.reduce((s, b) => s + b.weight, 0);
  const selVolume = selectedBoxes.reduce((s, b) => s + b.volume, 0);
  const selDensity = selVolume > 0 ? selWeight / selVolume : 0;

  // Генерирует имя файла: PL{дата}{код_клиента}-{порядковый}
  const packingListFileName = () => {
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const codes = [...new Set(
      balance.flatMap(g => g.boxes)
        .filter(b => selectedBoxIds.has(b.id))
        .map(b => b.counterparty_code || "")
        .filter(Boolean)
    )].join("_");
    // Порядковый номер — количество существующих листов + 1 (упрощённо)
    const seq = String(Date.now()).slice(-4);
    return `PL${date}${codes ? "_" + codes : ""}-${seq}.pdf`;
  };

  const handlePackingList = async () => {
    if (!selectedBoxIds.size) {
      message.warning(t("warehouse.no_boxes_selected"));
      return;
    }
    try {
      const res = await generatePackingListPreview([...selectedBoxIds]);
      downloadBlob(res.data as Blob, packingListFileName());
    } catch (e: any) {
      message.error("Ошибка генерации PDF");
    }
  };

  // Задача 1: печать QR на термопринтер этикеток 80×60 — PDF с N страницами
  const handlePrintAllQr = async () => {
    if (!selectedBoxIds.size) { message.warning(t("warehouse.no_boxes_selected")); return; }
    try {
      const res = await generateQrBulkPdf([...selectedBoxIds]);
      // Открываем PDF в новой вкладке — браузер или Acrobat напечатает через диалог
      const url = URL.createObjectURL(res.data as Blob);
      const win = window.open(url, "_blank");
      if (!win) downloadBlob(res.data as Blob, "labels.pdf");
    } catch (e: any) {
      message.error(e.response?.data?.detail || "Ошибка генерации PDF этикеток");
    }
  };

  const handleShip = async (codes: string[]) => {
    try {
      const res = await shipBoxes(codes);
      // Используем количество отправленных кодов — надёжнее header (CORS может блокировать)
      const shippedCount = codes.length;
      downloadBlob(res.data as Blob, `packing_list_${new Date().toISOString().slice(0, 10)}.pdf`);
      message.success(
        t("warehouse.ship_success", { count: shippedCount })
      );
      setSelectedBoxIds(new Set());
      qc.invalidateQueries({ queryKey: ["warehouse-balance"] });
    } catch (e: any) {
      // responseType:"blob" — тело ошибки тоже Blob, читаем как текст
      let errText = "Ошибка отгрузки";
      try {
        const blob: Blob = e.response?.data;
        if (blob instanceof Blob) {
          const text = await blob.text();
          const json = JSON.parse(text);
          errText = json.detail || errText;
        } else if (typeof e.response?.data?.detail === "string") {
          errText = e.response.data.detail;
        }
      } catch {}
      message.error({ content: errText, duration: 6 });
      throw e;
    }
  };

  const boxColumns: ColumnsType<WarehouseBox> = [
    {
      key: "select",
      width: 36,
      render: (_, b) => (
        <Checkbox checked={isBoxSelected(b.id)} onChange={() => toggleBox(b.id)} />
      ),
    },
    {
      title: "",
      key: "photo",
      width: 44,
      render: (_, b) =>
        b.photo_url ? (
          <Image
            src={b.photo_url}
            width={36}
            height={36}
            style={{ objectFit: "cover", borderRadius: 4 }}
            preview={{ mask: false }}
          />
        ) : (
          <div
            style={{
              width: 36,
              height: 36,
              background: "#f0f0f0",
              borderRadius: 4,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              color: "#ccc",
            }}
          >
            <InboxOutlined />
          </div>
        ),
    },
    {
      title: t("warehouse.item_name"),
      dataIndex: "item_name",
      key: "item_name",
      render: (v, b) => {
        const hasItems = b.items && b.items.length > 0;
        return (
          <div>
            <div style={{ fontWeight: 500 }}>{v}</div>
            {b.description && (
              <div style={{ fontSize: 11, color: "#888" }}>{b.description}</div>
            )}
            {/* Баг 3: позиции раскрываются/закрываются */}
            {hasItems && (
              <Collapse ghost size="small" style={{ marginTop: 2 }}>
                <Panel
                  key="items"
                  header={
                    <Text style={{ fontSize: 11, color: "#1677ff" }}>
                      {t("warehouse.box_items_collapse")} ({b.items.length})
                    </Text>
                  }
                  style={{ padding: 0 }}
                >
                  <div style={{ paddingLeft: 8, borderLeft: "2px solid #e8e8e8" }}>
                    {b.items.map((it: BoxItemData) => (
                      <div key={it.id} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                        {it.photos && it.photos.length > 0 && it.photos.map(p => (
                          <Image key={p.id} src={p.photo_url} width={24} height={24}
                            style={{ objectFit: "cover", borderRadius: 3, flexShrink: 0 }} />
                        ))}
                        <Text style={{ fontSize: 12 }}>{it.name}</Text>
                        <Tag style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                          ×{it.quantity}
                        </Tag>
                        {it.tracking_code && (
                          <Text type="secondary" style={{ fontSize: 10 }}>🔖{it.tracking_code}</Text>
                        )}
                      </div>
                    ))}
                  </div>
                </Panel>
              </Collapse>
            )}
            <div style={{ fontSize: 11, color: "#aaa" }}>{b.box_code}</div>
          </div>
        );
      },
    },
    {
      title: t("warehouse.tracking_code"),
      dataIndex: "tracking_number",
      key: "tracking_number",
      width: 130,
      render: (v: string | null) => v ? <Text style={{ fontSize: 11, fontFamily: "monospace" }}>{v}</Text> : "—",
    },
    {
      title: t("warehouse.warehouse_col"),
      dataIndex: "warehouse_name",
      key: "warehouse",
      width: 100,
      render: (v: string | null) => v ? <Tag color="blue" style={{ fontSize: 11 }}>{v}</Tag> : "—",
    },
    {
      title: t("warehouse.received_by"),
      dataIndex: "received_by_name",
      key: "received_by",
      width: 100,
      render: (v: string | null) => v ? <Text style={{ fontSize: 11 }}>{v}</Text> : "—",
    },
    {
      title: t("warehouse.weight"),
      dataIndex: "weight",
      key: "weight",
      width: 90,
      align: "right",
      render: (v) => <Text>{fmtNum(v)}</Text>,
    },
    {
      title: t("warehouse.volume"),
      dataIndex: "volume",
      key: "volume",
      width: 90,
      align: "right",
      render: (v) => <Text>{fmtNum(v, 4)}</Text>,
    },
    {
      title: t("warehouse.density"),
      dataIndex: "density",
      key: "density",
      width: 80,
      align: "right",
      render: (v) => <Text type="secondary">{fmtNum(v)}</Text>,
    },
    {
      title: "",
      key: "actions",
      width: 90,
      render: (_, b) => (
        <Space size={4}>
          <Button
            size="small"
            icon={<QrcodeOutlined />}
            onClick={async () => {
              try {
                const res = await apiClient.get(getQrLabelUrl(b.id), { responseType: "blob" });
                downloadBlob(res.data as Blob, `${b.box_code}.pdf`);
              } catch {
                message.error("Ошибка генерации наклейки");
              }
            }}
          />
          <Button size="small" icon={<EditOutlined />} onClick={() => setEditBox(b)} />
          <Popconfirm
            title={t("warehouse.delete_box_confirm", { code: b.box_code })}
            onConfirm={() => deleteMut.mutate(b.id)}
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
      {/* Toolbar */}
      <Row gutter={[12, 12]} align="middle" style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Select
            value={selectedWarehouseId}
            onChange={setSelectedWarehouseId}
            placeholder={t("warehouse.all_warehouses")}
            allowClear
            style={{ width: "100%" }}
          >
            {warehouses.map((w) => (
              <Option key={w.id} value={w.id}>
                {w.name}
              </Option>
            ))}
          </Select>
        </Col>
        <Col xs={24} sm={8}>
          <Input
            placeholder={t("warehouse.search_by_code")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
          />
        </Col>
        <Col xs={12} sm={4}>
          <Button
            type="primary"
            icon={<InboxOutlined />}
            onClick={() => setReceiptOpen(true)}
            block
            style={{ minHeight: 40 }}
          >
            {t("warehouse.receipt")}
          </Button>
        </Col>
        <Col xs={12} sm={4}>
          <Button
            icon={<QrcodeOutlined />}
            onClick={() => setShipOpen(true)}
            block
            danger
            style={{ minHeight: 40 }}
          >
            {t("warehouse.shipment")}
          </Button>
        </Col>
      </Row>

      {/* Selection bar */}
      {selectedBoxIds.size > 0 && (
        <div
          style={{
            background: "#e6f7ff",
            border: "1px solid #91d5ff",
            borderRadius: 6,
            padding: "8px 16px",
            marginBottom: 12,
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Text>
            {t("warehouse.selected_summary", {
              count: selectedBoxIds.size,
              weight: fmtNum(selWeight),
              volume: fmtNum(selVolume, 4),
            })}
            {" · "}{t("warehouse.density")}: {fmtNum(selDensity)}
          </Text>
          <Button
            type="primary"
            size="small"
            icon={<FilePdfOutlined />}
            onClick={handlePackingList}
          >
            {t("warehouse.create_packing_list")}
          </Button>
          {/* Задача 3: печать всех QR выбранных коробок */}
          <Button size="small" icon={<QrcodeOutlined />} onClick={handlePrintAllQr}>
            {t("warehouse.print_all_qr_count", { count: selectedBoxIds.size })}
          </Button>
          <Button size="small" onClick={() => setSelectedBoxIds(new Set())}>
            {t("warehouse.clear_selection")}
          </Button>
        </div>
      )}

      {/* Balance */}
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
        </div>
      ) : balance.length === 0 ? (
        <Empty description={t("warehouse.no_boxes_on_warehouse")} />
      ) : (
        <Collapse
          activeKey={expandedClients}
          onChange={(keys) => setExpandedClients(keys as string[])}
        >
          {balance.map((group) => {
            const groupIds = group.boxes.map((b) => b.id);
            const allGroupSelected = groupIds.every((id) => selectedBoxIds.has(id));
            const someGroupSelected = groupIds.some((id) => selectedBoxIds.has(id));

            return (
              <Panel
                key={group.counterparty_id}
                header={
                  <Row align="middle" gutter={12} wrap={false}>
                    <Col>
                      <Checkbox
                        checked={allGroupSelected}
                        indeterminate={someGroupSelected && !allGroupSelected}
                        onChange={() => toggleGroup(group)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Col>
                    <Col flex="auto">
                      <Space wrap>
                        <Text strong style={{ fontSize: 14 }}>
                          {group.counterparty_code || group.counterparty_name}
                        </Text>
                        {group.counterparty_code && (
                          <Text type="secondary">{group.counterparty_name}</Text>
                        )}
                        <Badge count={group.boxes_count} style={{ background: "#1677ff" }} />
                      </Space>
                    </Col>
                    <Col>
                      <Space size={16} style={{ fontSize: 12, color: "#666" }}>
                        <span>{fmtNum(group.sum_weight)} кг</span>
                        <span>{fmtNum(group.sum_volume, 4)} м³</span>
                        <span>ρ {fmtNum(group.total_density)}</span>
                      </Space>
                    </Col>
                  </Row>
                }
              >
                <Table
                  dataSource={group.boxes}
                  columns={boxColumns}
                  rowKey="id"
                  pagination={false}
                  size="small"
                  scroll={{ x: 600 }}
                  summary={(rows) => {
                    const tw = rows.reduce((s, b) => s + b.weight, 0);
                    const tv = rows.reduce((s, b) => s + b.volume, 0);
                    const td = tv > 0 ? tw / tv : 0;
                    return (
                      <Table.Summary.Row style={{ background: "#fafafa", fontWeight: 600 }}>
                        <Table.Summary.Cell index={0} colSpan={6}>
                          {t("warehouse.subtotal_label")} ({rows.length} {t("warehouse.places_unit")})
                        </Table.Summary.Cell>
                        <Table.Summary.Cell index={6} align="right">{fmtNum(tw)}</Table.Summary.Cell>
                        <Table.Summary.Cell index={7} align="right">{fmtNum(tv, 4)}</Table.Summary.Cell>
                        <Table.Summary.Cell index={8} align="right">{fmtNum(td)}</Table.Summary.Cell>
                        <Table.Summary.Cell index={9} />
                      </Table.Summary.Row>
                    );
                  }}
                />
              </Panel>
            );
          })}
        </Collapse>
      )}

      {/* Общий итог по всем клиентам */}
      {balance.length > 0 && (
        <div style={{
          marginTop: 16,
          padding: "12px 16px",
          background: "#1a4e7a",
          borderRadius: 6,
          color: "#fff",
          display: "flex",
          flexWrap: "wrap",
          gap: 24,
          alignItems: "center",
        }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{t("warehouse.total_label")}</span>
          <span>{t("warehouse.total_clients")}: <b>{balance.length}</b></span>
          <span>{t("warehouse.total_places")}: <b>{balance.reduce((s, g) => s + g.boxes_count, 0)}</b></span>
          <span>{t("warehouse.total_weight_label")}: <b>{fmtNum(balance.reduce((s, g) => s + g.sum_weight, 0))} кг</b></span>
          <span>{t("warehouse.total_volume_label")}: <b>{fmtNum(balance.reduce((s, g) => s + g.sum_volume, 0), 4)} м³</b></span>
          <span>{t("warehouse.total_density_label")}: <b>{(() => {
            const w = balance.reduce((s, g) => s + g.sum_weight, 0);
            const v = balance.reduce((s, g) => s + g.sum_volume, 0);
            return v > 0 ? fmtNum(w / v) : "—";
          })()}</b></span>
        </div>
      )}

      {/* Modals */}
      <ReceiptModal
        open={receiptOpen}
        warehouses={warehouses}
        defaultClientId={lastClientId}
        onSuccess={(boxes) => {
          // Запоминаем клиента для следующей приёмки (задача 4)
          if (boxes.length > 0) setLastClientId(boxes[0].counterparty_id);
          qc.invalidateQueries({ queryKey: ["warehouse-balance"] });
        }}
        onClose={() => setReceiptOpen(false)}
      />
      <QrScanModal
        open={shipOpen}
        onShip={handleShip}
        onClose={() => setShipOpen(false)}
      />
      <EditBoxModal
        box={editBox}
        onClose={() => setEditBox(null)}
        onSaved={() => qc.invalidateQueries({ queryKey: ["warehouse-balance"] })}
      />
    </div>
  );
}

// ── Warehouse Directory Tab ───────────────────────────────────────────────────

function WarehouseDirectoryTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingWarehouse, setEditingWarehouse] = useState<Warehouse | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => getWarehouses().then((r) => r.data),
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
    { title: t("warehouse.name"), dataIndex: "name", key: "name" },
    { title: t("warehouse.name_cn"), dataIndex: "name_cn", key: "name_cn" },
    { title: t("warehouse.city"), dataIndex: "city", key: "city" },
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
      <Row justify="end" style={{ marginBottom: 16 }}>
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

// ── History Tab ───────────────────────────────────────────────────────────────

function HistoryTab() {
  const { t } = useTranslation();

  const { data: shipped = [], isLoading: loadingBoxes } = useQuery({
    queryKey: ["warehouse-shipped"],
    queryFn: () => getShipped().then((r) => r.data),
  });

  const { data: packingLists = [], isLoading: loadingPL } = useQuery({
    queryKey: ["warehouse-packing-lists"],
    queryFn: () => getPackingLists().then((r) => r.data),
  });

  const boxColumns: ColumnsType<WarehouseBox> = [
    {
      title: t("warehouse.box_code"),
      dataIndex: "box_code",
      key: "box_code",
      render: (v) => <Text strong style={{ fontFamily: "monospace" }}>{v}</Text>,
    },
    {
      title: t("warehouse.client"),
      key: "client",
      render: (_, b) => (
        <span>{b.counterparty_code ? <Tag>{b.counterparty_code}</Tag> : null} {b.counterparty_name}</span>
      ),
    },
    { title: t("warehouse.item_name"), dataIndex: "item_name", key: "item_name" },
    { title: t("warehouse.shipping_warehouse"), dataIndex: "warehouse_name", key: "warehouse", width: 110,
      render: (v: string | null) => v ? <Tag color="blue" style={{ fontSize: 11 }}>{v}</Tag> : "—" },
    { title: t("warehouse.weight"), dataIndex: "weight", key: "weight", align: "right", width: 90,
      render: (v) => `${fmtNum(v)} кг` },
    { title: t("warehouse.volume"), dataIndex: "volume", key: "volume", align: "right", width: 90,
      render: (v) => `${fmtNum(v, 4)} м³` },
    { title: t("warehouse.received_at"), dataIndex: "received_at", key: "received_at", width: 130,
      render: (v: string | null) => v ? new Date(v).toLocaleDateString("ru-RU") : "—" },
    { title: t("warehouse.shipped_at"), dataIndex: "shipped_at", key: "shipped_at", width: 130,
      render: (v: string | null) => v ? new Date(v).toLocaleDateString("ru-RU") : "—" },
    { title: t("warehouse.received_by"), dataIndex: "received_by_name", key: "received_by", width: 110,
      render: (v: string | null) => v ? <Text style={{ fontSize: 11 }}>{v}</Text> : "—" },
    { title: t("warehouse.shipped_by"), dataIndex: "shipped_by_name", key: "shipped_by", width: 110,
      render: (v: string | null) => v ? <Text style={{ fontSize: 11 }}>{v}</Text> : "—" },
  ];

  const plColumns: ColumnsType<PackingListRecord> = [
    {
      title: t("warehouse.shipped_at"),
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (v) => new Date(v).toLocaleString("ru-RU"),
    },
    {
      title: t("warehouse.client"),
      key: "clients",
      render: (_, pl) => (
        <Space size={4} wrap>
          {(pl.clients || []).map((c) => <Tag key={c}>{c}</Tag>)}
        </Space>
      ),
    },
    { title: t("warehouse.boxes_count"), dataIndex: "total_boxes", key: "total_boxes", width: 80, align: "right" },
    { title: t("warehouse.sum_weight"), dataIndex: "total_weight", key: "total_weight", align: "right", width: 100,
      render: (v) => v ? `${fmtNum(v)} кг` : "—" },
    { title: t("warehouse.sum_volume"), dataIndex: "total_volume", key: "total_volume", align: "right", width: 100,
      render: (v) => v ? `${fmtNum(v, 4)} м³` : "—" },
    {
      title: "PDF",
      key: "pdf",
      width: 80,
      render: (_, pl) => pl.pdf_url ? (
        <Button
          size="small"
          icon={<FilePdfOutlined />}
          type="link"
          onClick={async () => {
            try {
              const res = await apiClient.get(pl.pdf_url!, { responseType: "blob" });
              const filename = pl.pdf_url!.split("/").pop() || "packing_list.pdf";
              downloadBlob(res.data as Blob, filename);
            } catch {
              message.error("Файл не найден на сервере");
            }
          }}
        >
          PDF
        </Button>
      ) : "—",
    },
  ];

  return (
    <div>
      <Title level={5} style={{ marginBottom: 12 }}>{t("warehouse.packing_list")} — {t("warehouse.shipped_history")}</Title>
      <Table
        dataSource={packingLists}
        columns={plColumns}
        rowKey="id"
        loading={loadingPL}
        pagination={false}
        size="small"
        scroll={{ x: "max-content" }}
        style={{ marginBottom: 32 }}
        locale={{ emptyText: t("warehouse.no_packing_lists") }}
      />

      <Title level={5} style={{ marginBottom: 12 }}>{t("warehouse.shipped_history")} — {t("warehouse.status_shipped")}</Title>
      <Table
        dataSource={shipped}
        columns={boxColumns}
        rowKey="id"
        loading={loadingBoxes}
        pagination={{ pageSize: 50, showSizeChanger: false }}
        size="small"
        scroll={{ x: "max-content" }}
        locale={{ emptyText: t("warehouse.no_shipped_yet") }}
      />
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function WarehousesPage(_props: Props) {
  const { t } = useTranslation();

  const { data: warehouses = [] } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => getWarehouses().then((r) => r.data),
  });

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        {t("warehouse.title")}
      </Title>
      <Tabs defaultActiveKey="balance" destroyInactiveTabPane={false}>
        <TabPane tab={t("warehouse.tab_balance")} key="balance">
          <BalanceTab warehouses={warehouses} />
        </TabPane>
        <TabPane tab={t("warehouse.shipped_history")} key="history">
          <HistoryTab />
        </TabPane>
        <TabPane tab={t("warehouse.tab_warehouses")} key="warehouses">
          <WarehouseDirectoryTab />
        </TabPane>
      </Tabs>
    </div>
  );
}
