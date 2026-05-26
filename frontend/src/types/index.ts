export type UserRole = "employee" | "manager" | "accountant" | "admin";
export type UserLang = "ru" | "zh";

export interface User {
  id: string;
  full_name: string;
  role: UserRole;
  lang: UserLang;
}
