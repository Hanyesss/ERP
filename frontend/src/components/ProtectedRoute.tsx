import { Navigate } from "react-router-dom";
import type { User } from "../types";

interface Props {
  user: User | null;
  loading: boolean;
  children: React.ReactNode;
}

export default function ProtectedRoute({ user, loading, children }: Props) {
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
