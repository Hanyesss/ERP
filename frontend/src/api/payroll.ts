import apiClient from "./client";

export interface PayrollEmployee {
  id: string;
  name: string;
  position?: string | null;
  is_active: boolean;
}

export interface PayrollRow {
  id: string;
  employee_id: string;
  employee_name: string;
  position?: string | null;
  role?: string | null;
  year: number;
  month: number;
  monthly_salary: number;
  working_days: number;
  social_insurance: number;
  taxes: number;
  bonus: number;
  is_paid: boolean;
  paid_at?: string | null;
  daily_rate: number;
  days_attended: number;
  overtime_hours: number;
  base_earned: number;
  overtime_pay: number;
  net_total: number;
}

export interface MonthData {
  year: number;
  month: number;
  days_in_month: number;
  rows: PayrollRow[];
  totals: { net_total: number; count: number };
}

export interface AttendanceDay {
  day: number;
  attended: boolean;
  overtime_hours: number;
}

export interface AvailableUser { user_id: string; full_name: string; role?: string | null; }

export const listEmployees = () => apiClient.get<PayrollEmployee[]>("/api/payroll/employees");
export const availableUsers = () => apiClient.get<AvailableUser[]>("/api/payroll/available-users");
export const createEmployee = (d: { user_id?: string; name?: string; position?: string }) =>
  apiClient.post("/api/payroll/employees", d);
export const patchEmployee = (id: string, d: Partial<{ name: string; position: string; is_active: boolean }>) =>
  apiClient.patch(`/api/payroll/employees/${id}`, d);

export const getMonth = (year: number, month: number) =>
  apiClient.get<MonthData>("/api/payroll/month", { params: { year, month } });

export const patchRecord = (
  id: string,
  d: Partial<{ monthly_salary: number; working_days: number; social_insurance: number; taxes: number; bonus: number }>,
) => apiClient.patch(`/api/payroll/records/${id}`, d);

export const getAttendance = (id: string) =>
  apiClient.get<{ record_id: string; year: number; month: number; days_in_month: number; days: AttendanceDay[] }>(
    `/api/payroll/records/${id}/attendance`,
  );

export const putAttendance = (id: string, days: AttendanceDay[]) =>
  apiClient.put(`/api/payroll/records/${id}/attendance`, days);

export const payRecord = (id: string, d: { cash_register_id: string; expense_date?: string; cash_rate?: number }) =>
  apiClient.post(`/api/payroll/records/${id}/pay`, d);
