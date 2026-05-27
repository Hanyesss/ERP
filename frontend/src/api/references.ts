import apiClient from "./client";

export interface Manager {
  id: string;
  full_name: string;
  role: string;
}

export interface BusinessType {
  id: string;
  name: string;
  name_cn?: string;
  code: string;
}

export interface ExpenseCategory {
  id: string;
  name: string;
  name_cn?: string;
}

export interface Employee {
  id: string;
  full_name: string;
}

export const getManagers = () =>
  apiClient.get<Manager[]>("/api/references/managers");

export const getBusinessTypes = () =>
  apiClient.get<BusinessType[]>("/api/references/business-types");

export const getExpenseCategories = () =>
  apiClient.get<ExpenseCategory[]>("/api/references/expense-categories");

export const getEmployees = () =>
  apiClient.get<Employee[]>("/api/references/employees");
