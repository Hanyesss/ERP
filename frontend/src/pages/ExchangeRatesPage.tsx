import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button, Col, DatePicker, Row, Table, Tag, Tooltip, Typography, message } from "antd";
import { EditOutlined, PlusOutlined, SyncOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { getExchangeRates, autoFetchRates } from "../api/exchangeRates";
import ExchangeRateForm from "../components/exchange-rates/ExchangeRateForm";
import type { ExchangeRate } from "../types/exchangeRate";

const { Title, Text } = Typography;

interface RatesByDate {
  date: string;
  rub?: ExchangeRate;
  usd?: ExchangeRate;
  usdt?: ExchangeRate;
}

function fmt(n: number, digits = 4) {
  return n.toFixed(digits);
}

export default function ExchangeRatesPage() {
  const { t } = useTranslation();
  const [modalOpen, setModalOpen] = useState(false);
  const [editDate, setEditDate] = useState<string | undefined>();
  const [editInitial, setEditInitial] = useState<any>(undefined);
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const qc = useQueryClient();

  const params = { date_from: dateRange?.[0], date_to: dateRange?.[1] };

  const autoFetch = useMutation({
    mutationFn: autoFetchRates,
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["exchange-rates"] });
      qc.invalidateQueries({ queryKey: ["exchange-rates-check"] });
      const d = res.data;
      const src = d.fetch_source === "moex" ? "MOEX" : "ЦБ РФ";
      const skipped = d.skipped_manual.length
        ? ` (пропущено с ручным курсом: ${d.skipped_manual.join(", ")})`
        : "";
      message.success(`Курсы обновлены с ${src}${skipped}`);
    },
    onError: () => message.error("Не удалось загрузить курсы с биржи"),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["exchange-rates", params],
    queryFn: () => getExchangeRates(params).then(r => r.data),
  });

  // Группируем записи по дате
  const grouped: RatesByDate[] = (() => {
    if (!data?.items) return [];
    const map: Record<string, RatesByDate> = {};
    for (const r of data.items) {
      if (!map[r.rate_date]) map[r.rate_date] = { date: r.rate_date };
      if (r.currency === "RUB") map[r.rate_date].rub = r;
      if (r.currency === "USD") map[r.rate_date].usd = r;
      if (r.currency === "USDT") map[r.rate_date].usdt = r;
    }
    return Object.values(map).sort((a, b) => b.date.localeCompare(a.date));
  })();

  const openEdit = (row: RatesByDate) => {
    const rubRate = row.rub ? parseFloat(String(row.rub.rate_to_cny)) : undefined;
    const usdRate = row.usd ? parseFloat(String(row.usd.rate_to_cny)) : undefined;
    const usdtRate = row.usdt ? parseFloat(String(row.usdt.rate_to_cny)) : undefined;
    setEditInitial({
      cny_to_rub: rubRate ? parseFloat((1 / rubRate).toFixed(4)) : undefined,
      usd_to_cny: usdRate ? parseFloat(usdRate.toFixed(4)) : undefined,
      usd_to_usdt: usdRate && usdtRate ? parseFloat((usdRate / usdtRate).toFixed(4)) : undefined,
    });
    setEditDate(row.date);
    setModalOpen(true);
  };

  const openCreate = () => {
    setEditInitial(undefined);
    setEditDate(dayjs().format("YYYY-MM-DD"));
    setModalOpen(true);
  };

  const sourceTag = (row: RatesByDate) => {
    const isManual = [row.rub, row.usd, row.usdt].some(r => r?.source === "manual");
    return isManual
      ? <Tooltip title="Курс задан вручную — авто-обновление пропускает этот день"><Tag color="gold">ручной</Tag></Tooltip>
      : <Tag color="green">авто</Tag>;
  };

  const columns = [
    {
      title: t("exchange_rate.date"),
      dataIndex: "date",
      key: "date",
      width: 120,
    },
    {
      title: "Источник",
      key: "source",
      width: 100,
      render: (_: any, row: RatesByDate) => sourceTag(row),
    },
    {
      title: "1 CNY = ? RUB",
      key: "cny_rub",
      width: 130,
      render: (_: any, row: RatesByDate) => {
        if (!row.rub) return <Text type="secondary">—</Text>;
        const v = 1 / parseFloat(String(row.rub.rate_to_cny));
        return <Text strong>{fmt(v)}</Text>;
      },
    },
    {
      title: "1 USD = ? RUB",
      key: "usd_rub",
      width: 130,
      render: (_: any, row: RatesByDate) => {
        if (!row.rub || !row.usd) return <Text type="secondary">—</Text>;
        const rub = parseFloat(String(row.rub.rate_to_cny));
        const usd = parseFloat(String(row.usd.rate_to_cny));
        return <Text>{fmt(usd / rub)}</Text>;
      },
    },
    {
      title: "1 USD = ? CNY",
      key: "usd_cny",
      width: 130,
      render: (_: any, row: RatesByDate) => {
        if (!row.usd) return <Text type="secondary">—</Text>;
        return <Text>{fmt(parseFloat(String(row.usd.rate_to_cny)))}</Text>;
      },
    },
    {
      title: "1 USD = ? USDT",
      key: "usd_usdt",
      width: 130,
      render: (_: any, row: RatesByDate) => {
        if (!row.usd || !row.usdt) return <Text type="secondary">—</Text>;
        const usd = parseFloat(String(row.usd.rate_to_cny));
        const usdt = parseFloat(String(row.usdt.rate_to_cny));
        return <Text>{fmt(usd / usdt)}</Text>;
      },
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 80,
      render: (_: any, row: RatesByDate) => (
        <Button icon={<EditOutlined />} size="small" onClick={() => openEdit(row)} />
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>{t("nav.exchange_rates")}</Title>
        </Col>
        <Col style={{ display: "flex", gap: 8 }}>
          <Button
            icon={<SyncOutlined />}
            loading={autoFetch.isPending}
            onClick={() => autoFetch.mutate()}
          >
            Обновить с биржи
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            {t("exchange_rate.add_new")}
          </Button>
        </Col>
      </Row>

      <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
        <Col>
          <DatePicker.RangePicker
            style={{ width: 260 }}
            onChange={(_, strs) => setDateRange(strs[0] && strs[1] ? [strs[0], strs[1]] : null)}
          />
        </Col>
      </Row>

      <Table scroll={{ x: "max-content" }}
        columns={columns}
        dataSource={grouped}
        rowKey="date"
        loading={isLoading}
        size="small"
        pagination={{ pageSize: 50, showTotal: total => `${total}` }}
      />

      <ExchangeRateForm
        open={modalOpen}
        defaultDate={editDate}
        initialRates={editInitial}
        onClose={() => { setModalOpen(false); setEditInitial(undefined); }}
      />
    </div>
  );
}
