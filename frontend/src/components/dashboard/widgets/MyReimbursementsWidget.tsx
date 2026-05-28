import { Card, Row, Col, Statistic, Button } from "antd";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

const fmt = (v: string | number) =>
  Number(v).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

export default function MyReimbursementsWidget({ data }: { data: any }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const by = data.by_status || {};
  return (
    <Card title={t("dashboard.my_reimbursements")} size="small">
      <Row gutter={12}>
        <Col span={12}>
          <Statistic title={t("expense.reimburse_pending")} value={by.pending?.cnt ?? 0} valueStyle={{ color: "#faad14" }} />
        </Col>
        <Col span={12}>
          <Statistic title={t("expense.reimburse_approved")} value={by.approved?.cnt ?? 0} valueStyle={{ color: "#1890ff" }} />
        </Col>
        <Col span={12} style={{ marginTop: 12 }}>
          <Statistic title={t("expense.reimburse_paid")} value={by.paid?.cnt ?? 0} valueStyle={{ color: "#3f8600" }} />
        </Col>
        <Col span={12} style={{ marginTop: 12 }}>
          <Statistic title={t("expense.reimburse_rejected")} value={by.rejected?.cnt ?? 0} valueStyle={{ color: "#cf1322" }} />
        </Col>
      </Row>
      <div style={{ marginTop: 16, padding: "12px 0", borderTop: "1px solid #f0f0f0" }}>
        <Statistic
          title={t("dashboard.company_owes_me")}
          value={fmt(data.balance_owed)}
          suffix="CNY"
          valueStyle={{ color: "#1890ff", fontSize: 20 }}
        />
      </div>
      <Button
        type="primary"
        block
        size="large"
        style={{ marginTop: 16 }}
        onClick={() => navigate("/expenses/new")}
      >
        {t("dashboard.create_reimbursement")}
      </Button>
    </Card>
  );
}
