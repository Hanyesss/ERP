import { Tag } from "antd";
import { useTranslation } from "react-i18next";
import type { OrderStatus, PaymentStatus } from "../../types/order";

const STATUS_COLORS: Record<string, string> = {
  new: "default",
  active: "blue",
  closed: "green",
  cancelled: "red",
};

const PAYMENT_COLORS: Record<string, string> = {
  unpaid: "red",
  partial: "gold",
  paid: "green",
};

const BT_COLORS: Record<string, string> = {
  trade: "blue",
  logistics: "green",
  services: "purple",
};

export function OrderStatusTag({ status }: { status: OrderStatus }) {
  const { t } = useTranslation();
  return <Tag color={STATUS_COLORS[status]}>{t(`order.status_${status}`)}</Tag>;
}

export function PaymentStatusTag({ status }: { status: PaymentStatus }) {
  const { t } = useTranslation();
  return <Tag color={PAYMENT_COLORS[status]}>{t(`order.payment_status_${status}`)}</Tag>;
}

export function BusinessTypeTag({ code, name, nameCn }: { code: string; name: string; nameCn?: string }) {
  const { i18n } = useTranslation();
  const label = i18n.language === "zh" && nameCn ? nameCn : name;
  return <Tag color={BT_COLORS[code] ?? "default"}>{label}</Tag>;
}
