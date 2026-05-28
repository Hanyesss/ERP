import { useState } from "react";
import { List, Button, Switch, Space, Typography, Empty, Popconfirm, Badge, Tag } from "antd";
import { CheckOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/ru";
import {
  getNotifications, markRead, markAllRead, deleteNotification,
  type NotificationItem,
} from "../api/notifications";

dayjs.extend(relativeTime);

const { Text, Title } = Typography;

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

export default function NotificationsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["notifications-page", unreadOnly, offset],
    queryFn: () => getNotifications({ unread_only: unreadOnly, limit, offset }).then(r => r.data),
  });

  const readMut = useMutation({
    mutationFn: (id: string) => markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications-page"] });
      qc.invalidateQueries({ queryKey: ["notif-count"] });
    },
  });

  const readAllMut = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications-page"] });
      qc.invalidateQueries({ queryKey: ["notif-count"] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteNotification(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications-page"] }),
  });

  const items: NotificationItem[] = data?.items || [];
  const total = data?.total || 0;

  return (
    <div style={{ maxWidth: 800 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          {t("nav.notifications")}
          {total > 0 && <Badge count={total} style={{ marginLeft: 8 }} />}
        </Title>
        <Space>
          <Switch
            checked={unreadOnly}
            onChange={v => { setUnreadOnly(v); setOffset(0); }}
            checkedChildren={t("notification.unread_only")}
            unCheckedChildren={t("notification.all")}
          />
          <Button icon={<CheckOutlined />} onClick={() => readAllMut.mutate()}>
            {t("notification.mark_all_read")}
          </Button>
        </Space>
      </div>

      {!isLoading && items.length === 0 && (
        <Empty description={t("notification.no_notifications")} />
      )}

      <List
        loading={isLoading}
        dataSource={items}
        renderItem={(item: NotificationItem) => (
          <List.Item
            style={{
              background: item.is_read ? "transparent" : "#e6f4ff",
              borderRadius: 6,
              padding: "10px 12px",
              marginBottom: 4,
              cursor: item.link ? "pointer" : "default",
            }}
            onClick={() => {
              if (!item.is_read) readMut.mutate(item.id);
              if (item.link) navigate(item.link);
            }}
            actions={[
              !item.is_read && (
                <Button
                  key="read"
                  size="small"
                  icon={<CheckOutlined />}
                  onClick={e => { e.stopPropagation(); readMut.mutate(item.id); }}
                />
              ),
              <Popconfirm
                key="del"
                title={t("notification.delete_confirm")}
                onConfirm={e => { e?.stopPropagation(); deleteMut.mutate(item.id); }}
                okText={t("common.yes")}
                cancelText={t("common.cancel")}
              >
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={e => e.stopPropagation()}
                />
              </Popconfirm>,
            ].filter(Boolean)}
          >
            <List.Item.Meta
              avatar={<span style={{ fontSize: 22 }}>{TYPE_ICONS[item.type] || "🔔"}</span>}
              title={
                <Space>
                  <span style={{ fontWeight: item.is_read ? 400 : 600 }}>{item.title}</span>
                  {!item.is_read && <Tag color="blue" style={{ fontSize: 10 }}>new</Tag>}
                </Space>
              }
              description={
                <div>
                  {item.body && <Text type="secondary">{item.body}</Text>}
                  <div style={{ fontSize: 11, color: "#aaa", marginTop: 2 }}>
                    {dayjs(item.created_at).locale("ru").fromNow()} ·{" "}
                    {dayjs(item.created_at).format("DD.MM.YYYY HH:mm")}
                  </div>
                </div>
              }
            />
          </List.Item>
        )}
        pagination={
          total > limit
            ? {
                current: offset / limit + 1,
                pageSize: limit,
                total,
                onChange: page => setOffset((page - 1) * limit),
                simple: true,
              }
            : false
        }
      />
    </div>
  );
}
