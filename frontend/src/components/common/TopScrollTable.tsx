/**
 * TopScrollTable — Table с двумя горизонтальными скроллбарами:
 * - СВЕРХУ (sticky, всегда видим под навбаром)
 * - СНИЗУ (стандартный ant-table)
 * Оба синхронизированы. Таблица скроллится в окне фиксированной высоты
 * (scroll.y), поэтому горизонтальный бегунок внизу тоже всегда в зоне видимости.
 */
import { useRef, useEffect, useCallback } from "react";
import { Table } from "antd";
import type { TableProps } from "antd";

// Высота области просмотра для таблицы (vh минус: навбар ~64 + фильтры ~120 + отступы)
const TABLE_BODY_HEIGHT = "calc(100vh - 260px)";

export default function TopScrollTable<T extends object>(props: TableProps<T>) {
  const topBarRef = useRef<HTMLDivElement>(null);
  const innerRef  = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const syncing   = useRef(false);

  // .ant-table-body появляется когда задан scroll.y; иначе .ant-table-content
  const getScrollEl = useCallback(() =>
    wrapperRef.current?.querySelector<HTMLElement>(".ant-table-body") ??
    wrapperRef.current?.querySelector<HTMLElement>(".ant-table-content"),
  []);

  const onTopBarScroll = useCallback(() => {
    if (syncing.current) return;
    const el = getScrollEl();
    if (!el || !topBarRef.current) return;
    syncing.current = true;
    el.scrollLeft = topBarRef.current.scrollLeft;
    syncing.current = false;
  }, [getScrollEl]);

  const onTableScroll = useCallback(() => {
    if (syncing.current) return;
    const el = getScrollEl();
    if (!el || !topBarRef.current) return;
    syncing.current = true;
    topBarRef.current.scrollLeft = el.scrollLeft;
    syncing.current = false;
  }, [getScrollEl]);

  const updateWidth = useCallback(() => {
    const el = getScrollEl();
    if (!el || !innerRef.current) return;
    const table = el.querySelector<HTMLElement>("table");
    innerRef.current.style.width = (table?.offsetWidth ?? el.scrollWidth) + "px";
  }, [getScrollEl]);

  useEffect(() => {
    let cleanup: (() => void) | undefined;
    const t = setTimeout(() => {
      const el = getScrollEl();
      if (!el) return;
      updateWidth();
      el.addEventListener("scroll", onTableScroll, { passive: true });
      const ro = new ResizeObserver(updateWidth);
      ro.observe(el);
      cleanup = () => { el.removeEventListener("scroll", onTableScroll); ro.disconnect(); };
    }, 150);
    return () => { clearTimeout(t); cleanup?.(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.dataSource]);

  // Подставляем scroll.y если не задан явно — фиксируем высоту тела таблицы
  const scroll = props.scroll?.y
    ? props.scroll
    : { ...props.scroll, y: TABLE_BODY_HEIGHT };

  return (
    <div ref={wrapperRef}>
      {/* Скроллбар сверху — sticky под навбаром */}
      <div ref={topBarRef} className="top-scroll-bar" onScroll={onTopBarScroll}>
        <div ref={innerRef} className="top-scroll-bar-inner" />
      </div>
      <Table {...props} scroll={scroll} />
    </div>
  );
}
