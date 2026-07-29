import { Button, Empty, Spin, message, Space } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import QuoteRequestCard from "./QuoteRequestCard";
import { getQuoteRequests, createQuoteRequest } from "../../api/logisticsQuotes";

interface Props { orderId: string }

export default function OrderQuotesTab({ orderId }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ["quote-requests", "order", orderId],
    queryFn: () => getQuoteRequests({ order_id: orderId }).then(r => r.data),
  });

  const refetch = () => qc.invalidateQueries({ queryKey: ["quote-requests"] });

  const createMut = useMutation({
    mutationFn: () => createQuoteRequest({ order_id: orderId }),
    onSuccess: () => { message.success("✓"); refetch(); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  if (isLoading) return <Spin />;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} loading={createMut.isPending}
          onClick={() => createMut.mutate()}>
          {t("quote.add_request")}
        </Button>
      </Space>
      {requests.length === 0 ? (
        <Empty description={t("quote.no_quotes_for_order")} />
      ) : (
        requests.map(r => <QuoteRequestCard key={r.id} request={r} onChanged={refetch} />)
      )}
    </div>
  );
}
