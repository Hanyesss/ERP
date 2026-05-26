import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button, Col, DatePicker, Row, Select, Table, Tag, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { getExchangeRates } from "../api/exchangeRates";
import ExchangeRateForm from "../components/exchange-rates/ExchangeRateForm";
import type { ExchangeRate } from "../types/exchangeRate";

const { Title } = Typography;

export default function ExchangeRatesPage() {
  const { t } = useTranslation();
  const [modalOpen, setModalOpen] = useState(false);
  const [currency, setCurrency] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);

  const params = {
    currency,
    date_from: dateRange?.[0],
    date_to: dateRange?.[1],
  };

  const { data, isLoading } = useQuery({
    queryKey: ["exchange-rates", params],
    queryFn: () => getExchangeRates(params).then(r => r.data),
  });

  const columns: ColumnsType<ExchangeRate> = [
    {
      title: t("exchange_rate.currency"),
      dataIndex: "currency",
      key: "currency",
      width: 100,
      render: (v) => <Tag color={v === "RUB" ? "blue" : "gold"}>{v}</Tag>,
    },
    {
      title: t("exchange_rate.rate"),
      dataIndex: "rate_to_cny",
      key: "rate_to_cny",
      width: 150,
      render: (v) => `${Number(v).toFixed(6)} CNY`,
    },
    {
      title: t("exchange_rate.date"),
      dataIndex: "rate_date",
      key: "rate_date",
      width: 130,
      defaultSortOrder: "descend",
      sorter: (a, b) => a.rate_date.localeCompare(b.rate_date),
    },
    {
      title: t("exchange_rate.source"),
      dataIndex: "source",
      key: "source",
      width: 100,
      render: (v) => (
        <Tag color={v === "auto" ? "green" : "default"}>
          {t(`exchange_rate.source_${v}`) || v}
        </Tag>
      ),
    },
    {
      title: t("common.created_by") || "Кто добавил",
      dataIndex: "created_by_name",
      key: "created_by_name",
    },
    {
      title: t("common.created_at") || "Дата добавления",
      dataIndex: "created_at",
      key: "created_at",
      render: (v) => new Date(v).toLocaleString("ru-RU"),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("nav.exchange_rates")}</Title>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            {t("exchange_rate.add_new")}
          </Button>
        </Col>
      </Row>

      <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
        <Col>
          <Select
            allowClear
            placeholder={t("exchange_rate.currency")}
            style={{ width: 120 }}
            options={[{ value: "RUB", label: "RUB" }, { value: "USDT", label: "USDT" }]}
            onChange={v => setCurrency(v)}
          />
        </Col>
        <Col>
          <DatePicker.RangePicker
            style={{ width: 240 }}
            onChange={(_, strs) => setDateRange(strs[0] && strs[1] ? [strs[0], strs[1]] : null)}
          />
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        size="small"
        pagination={{ pageSize: 50, showTotal: total => `${total}` }}
      />

      <ExchangeRateForm
        open={modalOpen}
        defaultDate={dayjs().format("YYYY-MM-DD")}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
