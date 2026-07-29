import { useEffect } from "react";

/**
 * Глобально позволяет вводить дробную часть и через запятую, и через точку
 * во всех числовых полях (antd InputNumber). Запятая заменяется на точку
 * прямо при наборе, значение корректно уходит в React onChange.
 */
export function useCommaDecimal() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "," && e.key !== "。" && e.key !== "，") return;
      const el = e.target as HTMLInputElement | null;
      if (!el || !el.classList || !el.classList.contains("ant-input-number-input")) return;

      e.preventDefault();
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      const next = el.value.slice(0, start) + "." + el.value.slice(end);

      // Нативный сеттер, чтобы React увидел изменение значения
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )?.set;
      setter?.call(el, next);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      const pos = start + 1;
      el.setSelectionRange(pos, pos);
    };

    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, []);
}
