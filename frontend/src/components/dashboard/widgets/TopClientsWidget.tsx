import { Card, Table, Empty } from "antd";
import { useTranslation } from "react-i18next";

const fmt = (v: number) =>
  v.toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export default function TopClientsWidget({ data }: { data: any[] }) {
  const { t } = useTranslation();
  return (
    <Card title={t("dashboard.top_clients")} size="small">
      {!data || data.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("common.no_data") || "Нет данных"} style={{ padding: "16px 0" }} />
      ) : (
        <Table
          dataSource={data}
          rowKey="client"
          size="small"
          pagination={false}
          columns={[
            { title: t("order.client"), dataIndex: "client", key: "client" },
            { title: `${t("dashboard.revenue")} CNY`, dataIndex: "revenue", key: "rev", align: "right",
              render: v => fmt(v) },
          ]}
        />
      )}
    </Card>
  );
}
