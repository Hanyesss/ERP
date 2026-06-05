import {
  Typography, Table, Tag, Button, Space, message, Tabs,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  getAdminPartners, getAdminPartnerPayouts, updateAdminPartnerPayout,
} from "../api/partner";
import type { AdminPartner, PartnerPayout, PartnerPayoutStatus } from "../types";

const STATUS_COLORS: Record<PartnerPayoutStatus, string> = {
  pending: "gold",
  approved: "blue",
  paid: "green",
  rejected: "red",
};

function fmt(n: number | string | undefined): string {
  const v = Number(n ?? 0);
  return v.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AdminPartnersPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: partners = [], isLoading: partnersLoading } = useQuery({
    queryKey: ["admin-partners"],
    queryFn: () => getAdminPartners().then((r) => r.data),
  });
  const { data: payouts = [], isLoading: payoutsLoading } = useQuery({
    queryKey: ["admin-partner-payouts"],
    queryFn: () => getAdminPartnerPayouts().then((r) => r.data),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateAdminPartnerPayout(id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-partner-payouts"] });
      qc.invalidateQueries({ queryKey: ["admin-partners"] });
      message.success(t("common.saved"));
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Error";
      message.error(typeof detail === "string" ? detail : JSON.stringify(detail));
    },
  });

  const partnerColumns: ColumnsType<AdminPartner> = [
    { title: t("partner.partner"), dataIndex: "partner_name", key: "partner_name" },
    { title: t("partner.accrued"), dataIndex: "total_accrued", key: "total_accrued", align: "right", render: (v) => fmt(v) },
    { title: t("partner.paid"), dataIndex: "total_paid", key: "total_paid", align: "right", render: (v) => fmt(v) },
    {
      title: t("partner.balance"), dataIndex: "balance", key: "balance", align: "right",
      render: (v) => <b style={{ color: Number(v) >= 0 ? "#3f8600" : "#cf1322" }}>{fmt(v)}</b>,
    },
  ];

  const payoutColumns: ColumnsType<PartnerPayout> = [
    { title: t("partner.date"), dataIndex: "created_at", key: "created_at", render: (v) => (v ? dayjs(v).format("YYYY-MM-DD") : "—") },
    { title: t("partner.partner"), dataIndex: "partner_name", key: "partner_name" },
    {
      title: t("partner.period"), key: "period",
      render: (_, r) => (r.period_from || r.period_to ? `${r.period_from ?? "..."} — ${r.period_to ?? "..."}` : t("partner.all_time")),
    },
    { title: t("partner.amount"), dataIndex: "amount", key: "amount", align: "right", render: (v) => fmt(v) },
    {
      title: t("partner.status"), dataIndex: "status", key: "status",
      render: (s: PartnerPayoutStatus) => <Tag color={STATUS_COLORS[s]}>{t(`partner.payout_status.${s}`)}</Tag>,
    },
    { title: t("partner.notes"), dataIndex: "notes", key: "notes" },
    {
      title: t("common.actions"), key: "actions", width: 280,
      render: (_, r) => (
        <Space>
          {r.status === "pending" && (
            <>
              <Button size="small" type="primary" loading={updateMut.isPending}
                onClick={() => updateMut.mutate({ id: r.id, status: "approved" })}>
                {t("partner.approve")}
              </Button>
              <Button size="small" danger loading={updateMut.isPending}
                onClick={() => updateMut.mutate({ id: r.id, status: "rejected" })}>
                {t("partner.reject")}
              </Button>
            </>
          )}
          {r.status === "approved" && (
            <Button size="small" type="primary" loading={updateMut.isPending}
              onClick={() => updateMut.mutate({ id: r.id, status: "paid" })}>
              {t("partner.mark_paid")}
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        {t("nav.admin_partners")}
      </Typography.Title>

      <Tabs
        defaultActiveKey="partners"
        items={[
          {
            key: "partners",
            label: t("partner.partners_tab"),
            children: (
              <Table
                scroll={{ x: "max-content" }}
                columns={partnerColumns}
                dataSource={partners}
                rowKey="partner_id"
                loading={partnersLoading}
                size="small"
                pagination={false}
              />
            ),
          },
          {
            key: "payouts",
            label: t("partner.payouts"),
            children: (
              <Table
                scroll={{ x: "max-content" }}
                columns={payoutColumns}
                dataSource={payouts}
                rowKey="id"
                loading={payoutsLoading}
                size="small"
                pagination={{ pageSize: 20 }}
              />
            ),
          },
        ]}
      />
    </div>
  );
}
