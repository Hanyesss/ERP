/**
 * TopScrollTable — Table обёртка с синхронизированным скроллбаром СВЕРХУ.
 * Скроллбар sticky: всегда виден, не нужно листать вниз чтобы скроллить горизонтально.
 */
import { useRef, useEffect, useCallback } from "react";
import { Table } from "antd";
import type { TableProps } from "antd";

export default function TopScrollTable<T extends object>(props: TableProps<T>) {
  const topBarRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  // Находим ant-table-content (содержит скроллируемую таблицу)
  const getTableContent = useCallback(() =>
    wrapperRef.current?.querySelector<HTMLElement>(".ant-table-content, .ant-table-body"),
  []);

  // Синхронизация: top-bar → table
  const onTopBarScroll = useCallback(() => {
    if (syncing.current) return;
    const tc = getTableContent();
    if (!tc || !topBarRef.current) return;
    syncing.current = true;
    tc.scrollLeft = topBarRef.current.scrollLeft;
    syncing.current = false;
  }, [getTableContent]);

  // Синхронизация: table → top-bar
  const onTableScroll = useCallback(() => {
    if (syncing.current) return;
    const tc = getTableContent();
    if (!tc || !topBarRef.current) return;
    syncing.current = true;
    topBarRef.current.scrollLeft = tc.scrollLeft;
    syncing.current = false;
  }, [getTableContent]);

  // Обновляем ширину inner-div чтобы top-bar знал реальную ширину контента
  const updateWidth = useCallback(() => {
    const tc = getTableContent();
    if (!tc || !innerRef.current) return;
    const table = tc.querySelector<HTMLElement>("table");
    innerRef.current.style.width = (table?.offsetWidth ?? tc.scrollWidth) + "px";
  }, [getTableContent]);

  useEffect(() => {
    // Ждём рендер таблицы
    const t = setTimeout(() => {
      const tc = getTableContent();
      if (!tc) return;
      updateWidth();
      tc.addEventListener("scroll", onTableScroll, { passive: true });
      // ResizeObserver для обновления ширины при изменении данных
      const ro = new ResizeObserver(updateWidth);
      ro.observe(tc);
      return () => {
        tc.removeEventListener("scroll", onTableScroll);
        ro.disconnect();
      };
    }, 100);
    return () => clearTimeout(t);
  }, [props.dataSource, getTableContent, onTableScroll, updateWidth]);

  return (
    <div ref={wrapperRef}>
      {/* Синхронизированный скроллбар сверху */}
      <div
        ref={topBarRef}
        className="top-scroll-bar"
        onScroll={onTopBarScroll}
      >
        <div ref={innerRef} className="top-scroll-bar-inner" />
      </div>
      <Table {...props} />
    </div>
  );
}
