"""Excel export service using openpyxl."""
from io import BytesIO
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

HEADERS = {
    "ru": {
        "pnl": {
            "metric": "Показатель",
            "current": "Текущий период",
            "prev": "Предыдущий период",
            "change_pct": "Изменение %",
            "revenue": "Входящие платежи",
            "outgoing": "Исходящие платежи",
            "expenses": "Расходы",
            "net_profit": "Чистая прибыль",
        },
        "by_client": ["Клиент", "Выручка", "Оплачено (клиентом)", "Оплачено (поставщику)", "Себестоимость", "Прямые расходы", "Представительские", "Чистая прибыль", "Долг"],
        "by_supplier": ["Поставщик", "Всего закуплено", "Оплачено", "Долг", "Кол-во", "Просрочка"],
        "expenses": ["Категория", "Сумма CNY", "%", "Кол-во"],
        "tonnage": {
            "summary": ["Вес (кг)", "Объём (м³)", "Кол-во заказов"],
            "by_warehouse": ["Склад", "Заказов", "Вес (кг)", "Объём (м³)"],
            "by_month": ["Год", "Месяц", "Вес (кг)", "Объём (м³)"],
            "detail": ["Номер заказа", "Дата", "Клиент", "Склад", "Вес (кг)", "Объём (м³)", "Создал"],
        },
    },
    "zh": {
        "pnl": {
            "metric": "指标",
            "current": "当前期间",
            "prev": "上期",
            "change_pct": "变化%",
            "revenue": "入账款",
            "outgoing": "出账款",
            "expenses": "费用",
            "net_profit": "净利润",
        },
        "by_client": ["客户", "收入", "客户已付", "已付供应商", "成本", "直接费用", "招待费", "净利润", "欠款"],
        "by_supplier": ["供应商", "采购总额", "已付", "欠款", "数量", "逾期"],
        "expenses": ["类别", "金额CNY", "%", "数量"],
        "tonnage": {
            "summary": ["重量(kg)", "体积(m³)", "订单数"],
            "by_warehouse": ["仓库", "订单数", "重量(kg)", "体积(m³)"],
            "by_month": ["年", "月", "重量(kg)", "体积(m³)"],
            "detail": ["订单号", "日期", "客户", "仓库", "重量(kg)", "体积(m³)", "创建人"],
        },
    },
}

HEADER_FILL = PatternFill("solid", fgColor="4472C4")
HEADER_FONT = Font(color="FFFFFF", bold=True)
ALT_FILL = PatternFill("solid", fgColor="EBF3FB")
BOLD_FONT = Font(bold=True)
GREEN_FONT = Font(color="375623", bold=True)
RED_FONT = Font(color="C00000", bold=True)

thin_border = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


def _auto_width(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, 10), 40)


def _header_row(ws, headers):
    row = ws.max_row + 1
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border


def _fmt(val):
    if val is None:
        return ""
    if isinstance(val, Decimal):
        return float(val)
    return val


def export_pnl(data: dict, lang: str = "ru") -> bytes:
    h = HEADERS.get(lang, HEADERS["ru"])["pnl"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "P&L"

    ws.append([h["metric"], h["current"], h["prev"], h["change_pct"]])
    for cell in ws[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = thin_border

    prev = data.get("prev_period", {})

    rows_data = [
        (h["revenue"], data.get("revenue"), prev.get("revenue"), data.get("pct_revenue")),
        (h["outgoing"], data.get("outgoing"), prev.get("outgoing"), None),
        (h["expenses"], data.get("expenses"), prev.get("expenses"), None),
        (h["net_profit"], data.get("net_profit"), prev.get("net_profit"), data.get("pct_net_profit")),
    ]
    profit_rows = {h["net_profit"]}

    for i, (label, curr_val, prev_val, pct) in enumerate(rows_data):
        row_num = ws.max_row + 1
        ws.cell(row=row_num, column=1, value=label)
        ws.cell(row=row_num, column=2, value=_fmt(curr_val))
        ws.cell(row=row_num, column=3, value=_fmt(prev_val))
        ws.cell(row=row_num, column=4, value=round(pct, 1) if pct is not None else "")

        for col in range(1, 5):
            cell = ws.cell(row=row_num, column=col)
            cell.border = thin_border
            if label in profit_rows:
                cell.font = BOLD_FONT
                cell.fill = PatternFill("solid", fgColor="FFFACD")

    _auto_width(ws)

    # Expense categories sheet
    ws2 = wb.create_sheet("Расходы по категориям" if lang == "ru" else "费用分类")
    ws2.append(["Категория" if lang == "ru" else "类别", "Название (кит.)" if lang == "ru" else "中文名", "Сумма CNY" if lang == "ru" else "金额CNY"])
    for cell in ws2[1]:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = thin_border

    for cat in data.get("expenses_by_category", []):
        ws2.append([cat.get("category_name"), cat.get("category_name_cn"), _fmt(cat.get("amount_cny"))])

    _auto_width(ws2)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_by_client(data: list, lang: str = "ru") -> bytes:
    headers = HEADERS.get(lang, HEADERS["ru"])["by_client"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "По клиентам" if lang == "ru" else "按客户"

    _header_row(ws, headers)

    _KEYS = ["revenue", "paid_by_client", "paid_to_supplier", "cogs", "direct_expenses", "client_expenses", "net_profit", "balance"]
    totals = {k: Decimal("0") for k in _KEYS}
    for i, row in enumerate(data):
        ws.append([
            row.get("client_name"),
            _fmt(row.get("revenue")),
            _fmt(row.get("paid_by_client")),
            _fmt(row.get("paid_to_supplier")),
            _fmt(row.get("cogs")),
            _fmt(row.get("direct_expenses")),
            _fmt(row.get("client_expenses")),
            _fmt(row.get("net_profit")),
            _fmt(row.get("balance")),
        ])
        for k in _KEYS:
            totals[k] += row.get(k, Decimal("0")) or Decimal("0")
        if i % 2 == 1:
            for col in range(1, 10):
                ws.cell(row=ws.max_row, column=col).fill = ALT_FILL

    # Summary row
    ws.append(["Итого" if lang == "ru" else "合计",
               _fmt(totals["revenue"]), _fmt(totals["paid_by_client"]), _fmt(totals["paid_to_supplier"]),
               _fmt(totals["cogs"]), _fmt(totals["direct_expenses"]), _fmt(totals["client_expenses"]),
               _fmt(totals["net_profit"]), _fmt(totals["balance"])])
    for col in range(1, 10):
        cell = ws.cell(row=ws.max_row, column=col)
        cell.font = BOLD_FONT
        cell.fill = PatternFill("solid", fgColor="D9E1F2")

    _auto_width(ws)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_by_supplier(data: list, lang: str = "ru") -> bytes:
    headers = HEADERS.get(lang, HEADERS["ru"])["by_supplier"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "По поставщикам" if lang == "ru" else "按供应商"

    _header_row(ws, headers)

    totals = {k: Decimal("0") for k in ["total_purchased_cny", "paid_cny", "debt_cny"]}
    total_count = 0
    for i, row in enumerate(data):
        overdue_label = ("Да" if lang == "ru" else "是") if row.get("has_overdue") else ""
        ws.append([
            row.get("supplier_name"),
            _fmt(row.get("total_purchased_cny")),
            _fmt(row.get("paid_cny")),
            _fmt(row.get("debt_cny")),
            row.get("count", 0),
            overdue_label,
        ])
        for k in totals:
            totals[k] += row.get(k, Decimal("0")) or Decimal("0")
        total_count += row.get("count", 0)
        if i % 2 == 1:
            for col in range(1, 7):
                ws.cell(row=ws.max_row, column=col).fill = ALT_FILL

    ws.append(["Итого" if lang == "ru" else "合计",
               _fmt(totals["total_purchased_cny"]), _fmt(totals["paid_cny"]),
               _fmt(totals["debt_cny"]), total_count, ""])
    for col in range(1, 7):
        cell = ws.cell(row=ws.max_row, column=col)
        cell.font = BOLD_FONT
        cell.fill = PatternFill("solid", fgColor="D9E1F2")

    _auto_width(ws)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_expenses(data: dict, lang: str = "ru") -> bytes:
    headers = HEADERS.get(lang, HEADERS["ru"])["expenses"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Расходы" if lang == "ru" else "费用"

    _header_row(ws, headers)

    for i, row in enumerate(data.get("items", [])):
        ws.append([
            row.get("category_name") if lang == "ru" else row.get("category_name_cn", row.get("category_name")),
            _fmt(row.get("amount_cny")),
            row.get("percent", 0),
            row.get("count", 0),
        ])
        if i % 2 == 1:
            for col in range(1, 5):
                ws.cell(row=ws.max_row, column=col).fill = ALT_FILL

    total_label = "Итого" if lang == "ru" else "合计"
    ws.append([total_label, _fmt(data.get("total")), 100.0, ""])
    for col in range(1, 5):
        cell = ws.cell(row=ws.max_row, column=col)
        cell.font = BOLD_FONT
        cell.fill = PatternFill("solid", fgColor="D9E1F2")

    _auto_width(ws)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_tonnage(data: dict, lang: str = "ru") -> bytes:
    th = HEADERS.get(lang, HEADERS["ru"])["tonnage"]
    wb = openpyxl.Workbook()

    # Summary sheet
    ws_sum = wb.active
    ws_sum.title = "Сводка" if lang == "ru" else "汇总"
    _header_row(ws_sum, th["summary"])
    ws_sum.append([
        _fmt(data.get("total_weight_kg")),
        _fmt(data.get("total_volume_m3")),
        data.get("order_count", 0),
    ])
    _auto_width(ws_sum)

    # By warehouse
    ws_wh = wb.create_sheet("По складам" if lang == "ru" else "按仓库")
    _header_row(ws_wh, th["by_warehouse"])
    for row in data.get("by_warehouse", []):
        name = row.get("warehouse_name_cn") if lang == "zh" else row.get("warehouse_name")
        ws_wh.append([name, row.get("order_count"), _fmt(row.get("total_weight_kg")), _fmt(row.get("total_volume_m3"))])
    _auto_width(ws_wh)

    # By month
    ws_mo = wb.create_sheet("По месяцам" if lang == "ru" else "按月")
    _header_row(ws_mo, th["by_month"])
    for row in data.get("by_month", []):
        ws_mo.append([row.get("year"), row.get("month"), _fmt(row.get("total_weight_kg")), _fmt(row.get("total_volume_m3"))])
    _auto_width(ws_mo)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_tonnage_detail(rows: list, lang: str = "ru") -> bytes:
    """Построчная детализация тоннажа с итоговой строкой."""
    th = HEADERS.get(lang, HEADERS["ru"])["tonnage"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Детализация" if lang == "ru" else "明细"
    _header_row(ws, th["detail"])

    total_w = Decimal("0")
    total_v = Decimal("0")
    for r in rows:
        wh = r.get("warehouse_name_cn") if lang == "zh" else r.get("warehouse_name")
        if not wh:
            wh = "仓库未指定" if lang == "zh" else "Склад не указан"
        weight = Decimal(str(r.get("total_weight_kg") or 0))
        volume = Decimal(str(r.get("total_volume_m3") or 0))
        total_w += weight
        total_v += volume
        ws.append([
            r.get("order_number"),
            str(r.get("order_date") or ""),
            r.get("client_name") or "",
            wh,
            _fmt(weight),
            _fmt(volume),
            r.get("created_by_name") or "",
        ])

    ws.append(["", "", "", "总计" if lang == "zh" else "Итого", _fmt(total_w), _fmt(total_v), ""])
    for cell in ws[ws.max_row]:
        cell.font = BOLD_FONT

    _auto_width(ws)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Названия типов операций кассы (совпадают с cash.op.* в локалях)
_CASH_OP_LABELS = {
    "ru": {
        "payment_in": "Входящий платёж", "payment_out": "Исходящий платёж",
        "payment_cancel": "Отмена платежа", "expense": "Расход",
        "reimbursement": "Выплата возмещения", "expense_cancel": "Отмена расхода",
        "transfer_out": "Перевод →", "transfer_in": "Перевод ←",
        "data_fix": "Корректировка данных",
    },
    "zh": {
        "payment_in": "收款", "payment_out": "付款", "payment_cancel": "取消付款",
        "expense": "支出", "reimbursement": "报销支出", "expense_cancel": "取消费用",
        "transfer_out": "转出 →", "transfer_in": "转入 ←", "data_fix": "数据校正",
    },
}

_CASH_HEADERS = {
    "ru": ["Дата", "Операция", "Приход", "Расход", "Баланс после", "Основание", "Создал"],
    "zh": ["日期", "操作", "收入", "支出", "余额", "事由", "创建人"],
}

_INVALID_SHEET = set(r'[]:*?/\\')


def _safe_sheet_title(name: str, used: set) -> str:
    """Корректное уникальное имя листа: <=31 симв., без недопустимых символов."""
    clean = "".join("_" if c in _INVALID_SHEET else c for c in (name or "Лист"))[:31] or "Лист"
    title = clean
    i = 2
    while title.lower() in used:
        suffix = f"_{i}"
        title = clean[:31 - len(suffix)] + suffix
        i += 1
    used.add(title.lower())
    return title


def export_cash_movements(registers: list, lang: str = "ru", period: str = "") -> bytes:
    """Движение средств: каждый кошелёк — отдельный лист.

    registers: список dict с ключами name, currency, opening_balance,
    closing_balance, total_in, total_out, rows[]. Каждая строка rows:
    date, operation_type, direction ('in'/'out'), amount, balance_after,
    reason, created_by.
    """
    ru = lang != "zh"
    headers = _CASH_HEADERS.get(lang, _CASH_HEADERS["ru"])
    op_labels = _CASH_OP_LABELS.get(lang, _CASH_OP_LABELS["ru"])
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # убираем пустой лист по умолчанию
    used_titles: set = set()

    if not registers:
        ws = wb.create_sheet("Пусто" if ru else "空")
        ws.append(["Нет данных" if ru else "无数据"])

    for reg in registers:
        ws = wb.create_sheet(_safe_sheet_title(reg.get("name", ""), used_titles))
        cur = reg.get("currency", "")

        # Шапка: название кошелька, валюта, период, входящий остаток
        ws.append([f"{reg.get('name', '')} ({cur})"])
        ws["A1"].font = Font(bold=True, size=13)
        if period:
            ws.append([("Период: " if ru else "期间：") + period])
        ws.append([
            ("Входящий остаток: " if ru else "期初余额：")
            + f"{_fmt(reg.get('opening_balance')):,.2f} {cur}"
        ])
        ws.append([])

        _header_row(ws, headers)
        for row in reg.get("rows", []):
            is_in = row.get("direction") == "in"
            amount = Decimal(str(row.get("amount") or 0))
            op = op_labels.get(row.get("operation_type") or "", row.get("operation_type") or "")
            ws.append([
                row.get("date") or "",
                op,
                _fmt(amount) if is_in else "",
                _fmt(amount) if not is_in else "",
                _fmt(row.get("balance_after")),
                row.get("reason") or "",
                row.get("created_by") or "",
            ])

        # Итоги: приход, расход, исходящий остаток
        ws.append([])
        total_in = reg.get("total_in") or Decimal("0")
        total_out = reg.get("total_out") or Decimal("0")
        ws.append([("Итого приход" if ru else "收入合计"), "", _fmt(total_in)])
        ws.append([("Итого расход" if ru else "支出合计"), "", "", _fmt(total_out)])
        ws.append([
            ("Исходящий остаток" if ru else "期末余额"), "", "", "",
            _fmt(reg.get("closing_balance")),
        ])
        for r_off in range(3):
            for cell in ws[ws.max_row - r_off]:
                cell.font = BOLD_FONT

        _auto_width(ws)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
