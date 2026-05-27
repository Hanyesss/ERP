import { useAuth } from "./useAuth";
import type { UserRole } from "../types";

export function useHasRole(role: UserRole): boolean {
  const { user } = useAuth();
  return user?.roles?.includes(role) ?? false;
}

export function useHasAnyRole(...roles: UserRole[]): boolean {
  const { user } = useAuth();
  if (!user?.roles) return false;
  return roles.some((r) => user.roles.includes(r));
}
