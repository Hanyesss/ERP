import { Card, Statistic, Row, Col } from "antd";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

const fmt = (v: string | number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export default function DebtsWidget({ data }: { data: any }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <Card title={t("dashboard.debts")} size="small">
      <Row gutter={16}>
        <Col span={12} style={{ cursor: "pointer" }} onClick={() => navigate("/orders")}>
          <Statistic
            title={t("dashboard.clients_owe_us")}
            value={fmt(data.receivable)}
            suffix="CNY"
            valueStyle={{ color: "#cf1322", fontSize: 18 }}
          />
        </Col>
        <Col span={12} style={{ cursor: "pointer" }} onClick={() => navigate("/purchases")}>
          <Statistic
            title={t("dashboard.we_owe_suppliers")}
            value={fmt(data.payable)}
            suffix="CNY"
            valueStyle={{ color: "#faad14", fontSize: 18 }}
          />
        </Col>
      </Row>
    </Card>
  );
}
