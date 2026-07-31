import { useState } from "react";
import { Badge, Button, Popover, List, Typography, Space, Divider, Empty } from "antd";
import { BellOutlined, CheckOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/ru";
import {
  getUnreadCount, getNotifications, markRead, markAllRead,
  type NotificationItem,
} from "../../api/notifications";

dayjs.extend(relativeTime);

const { Text } = Typography;

const TYPE_ICONS: Record<string, string> = {
  reimbursement_created: "💰",
  reimbursement_approved: "✅",
  reimbursement_rejected: "❌",
  reimbursement_paid: "💸",
  order_paid: "🎉",
  purchase_created: "📦",
  purchase_paid: "✅",
  payment_unassigned: "⚠️",
  order_overdue: "⏰",
};

function NotifItem({ item, onRead }: { item: NotificationItem; onRead: (id: string, link?: string) => void }) {
  const { t, i18n } = useTranslation();
  const title = t(`notification.types.${item.type}`, { defaultValue: item.title });
  const locale = i18n.language === "zh" ? "zh-cn" : "ru";
  return (
    <List.Item
      style={{
        padding: "8px 0",
        cursor: item.link ? "pointer" : "default",
        background: item.is_read ? "transparent" : "#e6f4ff",
        borderRadius: 4,
        paddingLeft: 8,
      }}
      onClick={() => onRead(item.id, item.link || undefined)}
    >
      <Space align="start" size={8}>
        <span style={{ fontSize: 18 }}>{TYPE_ICONS[item.type] || "🔔"}</span>
        <div>
          <div style={{ fontWeight: item.is_read ? 400 : 600, fontSize: 13 }}>{title}</div>
          {item.body && <Text type="secondary" style={{ fontSize: 12 }}>{item.body}</Text>}
          <div style={{ fontSize: 11, color: "#aaa", marginTop: 2 }}>
            {dayjs(item.created_at).locale(locale).fromNow()}
          </div>
        </div>
      </Space>
    </List.Item>
  );
}

export default function NotificationBell() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const { data: countData } = useQuery({
    queryKey: ["notif-count"],
    queryFn: () => getUnreadCount().then(r => r.data),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const { data: listData } = useQuery({
    queryKey: ["notif-list"],
    queryFn: () => getNotifications({ limit: 10 }).then(r => r.data),
    enabled: open,
    staleTime: 10_000,
  });

  const readMut = useMutation({
    mutationFn: markRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notif-count"] });
      qc.invalidateQueries({ queryKey: ["notif-list"] });
    },
  });

  const readAllMut = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notif-count"] });
      qc.invalidateQueries({ queryKey: ["notif-list"] });
    },
  });

  const handleRead = (id: string, link?: string) => {
    readMut.mutate(id);
    if (link) {
      navigate(link);
      setOpen(false);
    }
  };

  const items = listData?.items || [];
  const unread = countData?.count || 0;

  const content = (
    <div style={{ width: "min(340px, calc(100vw - 24px))" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <Text strong>{t("notification.title")}</Text>
        {unread > 0 && (
          <Button size="small" icon={<CheckOutlined />} onClick={() => readAllMut.mutate()}>
            {t("notification.mark_all_read")}
          </Button>
        )}
      </div>
      <Divider style={{ margin: "4px 0 8px" }} />
      {items.length === 0 ? (
        <Empty description={t("notification.no_unread")} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          dataSource={items}
          renderItem={item => (
            <NotifItem key={item.id} item={item} onRead={handleRead} />
          )}
          size="small"
        />
      )}
      <Divider style={{ margin: "8px 0 4px" }} />
      <Button
        type="link"
        size="small"
        block
        onClick={() => { navigate("/notifications"); setOpen(false); }}
      >
        {t("notification.show_all")}
      </Button>
    </div>
  );

  return (
    <Popover
      content={content}
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="bottomRight"
      arrow={false}
      overlayStyle={{ maxWidth: "calc(100vw - 12px)" }}
    >
      <Badge count={unread} size="small" offset={[-2, 2]}>
        <Button type="text" icon={<BellOutlined style={{ fontSize: 18 }} />} />
      </Badge>
    </Popover>
  );
}
