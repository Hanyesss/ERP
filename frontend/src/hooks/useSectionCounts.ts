import { useState, useEffect, useCallback, useRef } from "react";
import apiClient from "../api/client";

export interface SectionCount {
  count: number;
  last_read_at: string | null;
}

export interface SectionCounts {
  orders: SectionCount | null;
  payments: SectionCount | null;
  expenses: SectionCount | null;
  purchases: SectionCount | null;
}

const POLL_INTERVAL = 30_000;

let globalCounts: SectionCounts | null = null;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

async function fetchCounts() {
  try {
    const res = await apiClient.get("/api/notifications/section-counts");
    globalCounts = res.data;
    notify();
  } catch {
    // ignore — пользователь не admin или нет сети
  }
}

// Синглтон-таймер — один на всё приложение
let timer: ReturnType<typeof setInterval> | null = null;
function ensurePolling() {
  if (timer) return;
  fetchCounts();
  timer = setInterval(fetchCounts, POLL_INTERVAL);
}

export function useSectionCounts() {
  const [counts, setCounts] = useState<SectionCounts | null>(globalCounts);

  useEffect(() => {
    const update = () => setCounts(globalCounts);
    listeners.add(update);
    ensurePolling();
    return () => { listeners.delete(update); };
  }, []);

  const markRead = useCallback(async (section: keyof SectionCounts) => {
    try {
      await apiClient.post(`/api/notifications/section-read/${section}`);
      await fetchCounts();
    } catch { /* ignore */ }
  }, []);

  // Возвращает last_read_at ДО markRead — для подсветки новых строк
  const getLastReadAt = useCallback((section: keyof SectionCounts): string | null => {
    return globalCounts?.[section]?.last_read_at ?? null;
  }, [counts]);

  return { counts, markRead, getLastReadAt, refresh: fetchCounts };
}
