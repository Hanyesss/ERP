import { useState, useEffect } from "react";
import type { User } from "../types";
import { getMe } from "../api/auth";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const delay = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
    getMe()
      .then((r) => setUser(r.data))
      .catch(() =>
        delay(1500)
          .then(() => getMe())
          .then((r) => setUser(r.data))
          .catch(() => setUser(null))
      )
      .finally(() => setLoading(false));
  }, []);

  return { user, setUser, loading };
}
