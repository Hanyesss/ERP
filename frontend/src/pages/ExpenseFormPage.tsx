import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Form, Input, Select, DatePicker, Button, Card, Typography,
  Space, Row, Col, InputNumber, Switch, Alert, message, Skeleton,
} from "antd";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation } from "@tanstack/react-query";
import dayjs from "dayjs";
import { createExpense, updateExpense, getExpense } from "../api/expenses";
import { getExpenseCategories, getEmployees } from "../api/references";
import { getOrders } from "../api/orders";
import { getExchangeRates } from "../api/exchangeRates";
import CounterpartySelect from "../components/common/CounterpartySelect";
import type { User } from "../types";

const { Title } = Typography;
const CURRENCIES = ["CNY", "RUB", "USDT", "USD"];

interface Props { user: User }

export default function ExpenseFormPage({ user }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const [form] = Form.useForm();

  const isAccountant = user.roles?.some(r => ["accountant", "admin"].includes(r));

  const [currency, setCurrency] = useState("CNY");
  const [rateToCny, setRateToCny] = useState(1);
  const [amount, setAmount] = useState(0);
  const [linkType, setLinkType] = useState("none");
  const [isReimbursement, setIsReimbursement] = useState(!isAccountant);
  const [initialized, setInitialized] = useState(false);

  const expenseDate: dayjs.Dayjs | null = Form.useWatch("expense_date", form);
  const dateStr = expenseDate?.format("YYYY-MM-DD");

  // Load existing data for edit mode
  const { data: existing, isLoading: existingLoading } = useQuery({
    queryKey: ["expense", id],
    queryFn: () => getExpense(id!).then(r => r.data),
    enabled: isEdit,
  });

  const { data: ratesData } = useQuery({
    queryKey: ["exchange-rates-list"],
    queryFn: () => getExchangeRates({}).then(r => r.data),
  });

  const { data: categories } = useQuery({
    queryKey: ["expense-categories"],
    queryFn: () => getExpenseCategories().then(r => r.data),
  });

  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => getEmployees().then(r => r.data),
    enabled: isAccountant,
  });

  const { data: ordersData } = useQuery({
    queryKey: ["orders-for-expense"],
    queryFn: () => getOrders({ page_size: 100 }).then(r => r.data),
    enabled: linkType === "order",
  });

  // Initialize form
  useEffect(() => {
    if (initialized) return;
    if (isEdit) {
      if (!existing) return;
      form.setFieldsValue({
        expense_date: dayjs(existing.expense_date),
        category_id: existing.category_id,
        currency: existing.currency,
        amount: Number(existing.amount),
        rate_to_cny: Number(existing.rate_to_cny),
        link_type: existing.link_type,
        order_id: existing.order_id,
        client_id: existing.client_id,
        description: existing.description,
        reimburse_to_user_id: existing.reimburse_to_user_id,
      });
      setCurrency(existing.currency);
      setRateToCny(Number(existing.rate_to_cny));
      setAmount(Number(existing.amount));
      setLinkType(existing.link_type);
      setIsReimbursement(existing.is_reimbursement);
      setInitialized(true);
    } else {
      form.setFieldsValue({
        expense_date: dayjs(),
        currency: "CNY",
        rate_to_cny: 1,
        link_type: "none",
      });
      setInitialized(true);
    }
  }, [isEdit, existing, form, initialized]);

  // Auto-fetch rate when currency/date changes (only in create mode)
  useEffect(() => {
    if (!initialized || isEdit) return;
    if (currency === "CNY") {
      setRateToCny(1);
      form.setFieldValue("rate_to_cny", 1);
      return;
    }
    if (!dateStr || !ratesData) return;
    const match = (ratesData.items || ratesData || []).find(
      (r: any) => r.currency === currency && r.rate_date === dateStr
    );
    if (match) {
      const rate = Number(match.rate_to_cny);
      setRateToCny(rate);
      form.setFieldValue("rate_to_cny", rate);
    }
  }, [currency, dateStr, ratesData, form, initialized, isEdit]);

  const amountCny = Number((amount * rateToCny).toFixed(2));
  const missingRate = currency !== "CNY" && rateToCny === 1 && !!dateStr;

  const createMutation = useMutation({
    mutationFn: createExpense,
    onSuccess: (res) => { message.success("✓"); navigate(`/expenses/${res.data.id}`); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const updateMutation = useMutation({
    mutationFn: (data: any) => updateExpense(id!, data),
    onSuccess: () => { message.success("✓"); navigate(`/expenses/${id}`); },
    onError: (e: any) => message.error(e.response?.data?.detail || "Error"),
  });

  const handleSubmit = (values: any) => {
    const payload = {
      expense_date: values.expense_date.format("YYYY-MM-DD"),
      category_id: values.category_id,
      currency: values.currency,
      amount: values.amount,
      rate_to_cny: values.rate_to_cny,
      link_type: values.link_type,
      order_id: values.link_type === "order" ? values.order_id : undefined,
      client_id: values.link_type === "client" ? values.client_id : undefined,
      description: values.description,
      ...(isAccountant && { reimburse_to_user_id: isReimbursement ? values.reimburse_to_user_id : undefined }),
    };

    if (isEdit) {
      updateMutation.mutate(payload);
    } else {
      createMutation.mutate({ ...payload, is_reimbursement: isReimbursement });
    }
  };

  const categoryOptions = (categories ?? []).map((c: any) => ({
    value: c.id,
    label: c.name_cn ? `${c.name} / ${c.name_cn}` : c.name,
  }));

  const orderOptions = (ordersData?.items ?? []).map((o: any) => ({
    value: o.id,
    label: `${o.order_number} — ${o.client_name ?? ""}`,
  }));

  const employeeOptions = (employees ?? []).map((e: any) => ({
    value: e.id,
    label: e.full_name,
  }));

  const isPending = createMutation.isPending || updateMutation.isPending;

  if (isEdit && existingLoading) return <Skeleton active />;

  return (
    <div style={{ maxWidth: 800 }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            {isEdit ? t("expense.edit_title") : t("expense.create_new")}
          </Title>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate(isEdit ? `/expenses/${id}` : "/expenses")}>
              {t("common.cancel")}
            </Button>
            <Button type="primary" onClick={() => form.submit()} loading={isPending}>
              {t("common.save")}
            </Button>
          </Space>
        </Col>
      </Row>

      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Card>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="expense_date" label={t("expense.date")} rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={16}>
              <Form.Item name="category_id" label={t("expense.category")} rules={[{ required: true }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  options={categoryOptions}
                  placeholder={t("expense.select_category")}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="currency" label={t("expense.currency")} rules={[{ required: true }]}>
                <Select
                  options={CURRENCIES.map(c => ({ value: c, label: c }))}
                  onChange={v => { setCurrency(v); }}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="amount" label={t("expense.amount")} rules={[{ required: true }]}>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={0.01}
                  onChange={v => setAmount(v ?? 0)}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="rate_to_cny" label={t("expense.rate_to_cny")} rules={[{ required: true }]}>
                <InputNumber
                  style={{ width: "100%" }}
                  min={0}
                  step={0.00001}
                  precision={8}
                  disabled={currency === "CNY"}
                  onChange={v => setRateToCny(v ?? 1)}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label={`${t("expense.amount_cny")} (CNY)`}>
                <InputNumber style={{ width: "100%" }} value={amountCny} disabled />
              </Form.Item>
            </Col>
          </Row>

          {missingRate && (
            <Alert
              type="warning"
              showIcon
              message={`Нет курса ${currency} на ${dateStr}. Введите курс вручную.`}
              style={{ marginBottom: 16 }}
            />
          )}

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="link_type" label={t("expense.link_type")} rules={[{ required: true }]}>
                <Select
                  options={[
                    { value: "none", label: t("expense.link_none") },
                    { value: "order", label: t("expense.link_order") },
                    { value: "client", label: t("expense.link_client") },
                  ]}
                  onChange={v => setLinkType(v)}
                />
              </Form.Item>
            </Col>

            {linkType === "order" && (
              <Col span={16}>
                <Form.Item name="order_id" label={t("expense.order")} rules={[{ required: true }]}>
                  <Select
                    showSearch
                    optionFilterProp="label"
                    options={orderOptions}
                    placeholder={t("expense.select_order")}
                  />
                </Form.Item>
              </Col>
            )}

            {linkType === "client" && (
              <Col span={16}>
                <Form.Item name="client_id" label={t("expense.client")} rules={[{ required: true }]}>
                  <CounterpartySelect type="client" placeholder={t("expense.select_client")} />
                </Form.Item>
              </Col>
            )}
          </Row>

          <Form.Item name="description" label={t("expense.description")} rules={[{ required: true }]}>
            <Input.TextArea rows={2} />
          </Form.Item>

          {isAccountant ? (
            <>
              {!isEdit && (
                <Form.Item label={t("expense.is_reimbursement")}>
                  <Switch
                    checked={isReimbursement}
                    onChange={v => setIsReimbursement(v)}
                    checkedChildren={t("expense.reimbursement")}
                    unCheckedChildren={t("expense.direct_expense")}
                  />
                </Form.Item>
              )}

              {isReimbursement && (
                <Form.Item name="reimburse_to_user_id" label={t("expense.reimburse_to")}>
                  <Select
                    showSearch
                    optionFilterProp="label"
                    options={employeeOptions}
                    placeholder={t("expense.select_employee_optional")}
                    allowClear
                  />
                </Form.Item>
              )}
            </>
          ) : (
            <Alert
              type="info"
              showIcon
              message={`${t("expense.reimburse_to")}: ${user.full_name}`}
              description={t("expense.reimbursement_self_info")}
              style={{ marginTop: 8 }}
            />
          )}
        </Card>
      </Form>
    </div>
  );
}
