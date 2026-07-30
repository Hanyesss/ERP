import { useState } from "react";
import {
  Typography, Button, Input, Row, Col, Modal, Form, Select, InputNumber,
  Segmented, message, Empty, Spin, Space,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import QuoteRequestCard from "../components/logistics/QuoteRequestCard";
import QuoteRequestFields from "../components/logistics/QuoteRequestFields";
import { getQuoteRequests, createQuoteRequest } from "../api/logisticsQuotes";
import { getOrders } from "../api/orders";
import { getBusinessTypes } from "../api/references";

const { Title } = Typography;

export default function QuotesComparisonPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [mode, setMode] = useState<"order" | "manual">("order");
  const [orderSearch, setOrderSearch] = useState("");
  const [form] = Form.useForm();

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ["quote-requests", search],
    queryFn: () => getQuoteRequests({ search: search || undefined }).then(r => r.data),
  });

  // Логистические заказы для выбора при создании заявки
  const { data: btData } = useQuery({
    queryKey: ["business-types"],
    queryFn: () => getBusinessTypes().then(r => r.data),
  });
  const logisticsBtId = (btData || []).find((b: any) => b.code === "logistics")?.id;

  const { data: ordersResp } = useQuery({
    queryKey: ["orders-for-quote", orderSearch, logisticsBtId],
    queryFn: () => getOrders({
      search: orderSearch || undefined,
      business_type_id: logisticsBtId,
      page: 1, page_size: 30,
    }).then(r => r.data),
    enabled: addOpen && mode === "order" && !!logisticsBtId,
  });
  const orderOptions = (ordersResp?.items || []).map((o: any) => ({
    value: o.id,
    label: `${o.order_number}${o.client_name ? " · " + o.client_name : ""}`,
  }));

  const refetch = () => {
    qc.invalidateQueries({ queryKey: ["quote-requests"] });
    qc.invalidateQueries({ queryKey: ["quotes-pending-count"] });
  };

  const createMut = useMutation({
    mutationFn: createQuoteRequest,
    onSuccess: () => { message.success("✓"); setAddOpen(false); form.resetFields(); refetch(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const submit = (v: any) => {
    if (mode === "order") {
      if (!v.order_id) { message.error(t("quote.pick_order")); return; }
      createMut.mutate({ order_id: v.order_id });
    } else {
      createMut.mutate({
        order_number: v.order_number,
        product_name: v.product_name,
        cargo_value: v.cargo_value,
        box: Array.isArray(v.box) ? v.box.join(", ") : v.box,
        dimensions: v.dimensions,
        volume_m3: v.volume_m3 ?? undefined,
        weight_kg: v.weight_kg ?? undefined,
        destination: v.destination,
        dispatch_place: v.dispatch_place,
        client_price: v.client_price ?? undefined,
      });
    }
  };

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col><Title level={4} style={{ margin: 0 }}>{t("quote.title")}</Title></Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setMode("order"); setAddOpen(true); }}>
            {t("quote.add_request")}
          </Button>
        </Col>
      </Row>

      <Input.Search
        placeholder={t("quote.search_placeholder")}
        allowClear
        style={{ width: 300, marginBottom: 16 }}
        onSearch={setSearch}
        onChange={e => { if (!e.target.value) setSearch(""); }}
      />

      {isLoading ? <Spin /> : requests.length === 0 ? (
        <Empty description={t("common.no_data")} />
      ) : (
        requests.map(r => <QuoteRequestCard key={r.id} request={r} onChanged={refetch} />)
      )}

      <Modal
        open={addOpen}
        title={t("quote.add_request")}
        onOk={() => form.validateFields().then(submit)}
        onCancel={() => { setAddOpen(false); form.resetFields(); }}
        confirmLoading={createMut.isPending}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        destroyOnClose
      >
        <Segmented
          block
          value={mode}
          onChange={v => setMode(v as any)}
          options={[
            { value: "order", label: t("quote.from_order") },
            { value: "manual", label: t("quote.manual") },
          ]}
          style={{ marginBottom: 16 }}
        />
        <Form form={form} layout="vertical" className="responsive-form">
          {mode === "order" ? (
            <Form.Item name="order_id" label={t("quote.logistics_order")} rules={[{ required: true }]}>
              <Select
                showSearch
                filterOption={false}
                onSearch={setOrderSearch}
                placeholder={t("quote.pick_order")}
                options={orderOptions}
                notFoundContent={t("common.no_data")}
              />
            </Form.Item>
          ) : (
            <QuoteRequestFields />
          )}
        </Form>
      </Modal>
    </div>
  );
}
