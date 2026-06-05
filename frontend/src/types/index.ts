export type UserRole = "employee" | "seller" | "manager" | "purchaser" | "accountant" | "admin";
export type UserLang = "ru" | "zh";

export interface User {
  id: string;
  full_name: string;
  roles: UserRole[];
  lang: UserLang;
}
