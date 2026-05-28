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
            "revenue": "Выручка",
            "cogs": "Себестоимость",
            "direct_expenses": "Прямые расходы",
            "gross_profit": "Маржинальная прибыль",
            "client_expenses": "Представительские",
            "general_expenses": "Общехозяйственные",
            "net_profit": "Чистая прибыль",
        },
        "by_client": ["Клиент", "Выручка", "Оплачено", "Себестоимость", "Прямые расходы", "Представительские", "Чистая прибыль", "Долг"],
        "by_supplier": ["Поставщик", "Всего закуплено", "Оплачено", "Долг", "Кол-во", "Просрочка"],
        "expenses": ["Категория", "Сумма CNY", "%", "Кол-во"],
        "tonnage": {
            "summary": ["Вес (кг)", "Объём (м³)", "Кол-во заказов"],
            "by_warehouse": ["Склад", "Заказов", "Вес (кг)", "Объём (м³)"],
            "by_month": ["Год", "Месяц", "Вес (кг)", "Объём (м³)"],
        },
    },
    "zh": {
        "pnl": {
            "metric": "指标",
            "current": "当前期间",
            "prev": "上期",
            "change_pct": "变化%",
            "revenue": "收入",
            "cogs": "销货成本",
            "direct_expenses": "直接费用",
            "gross_profit": "毛利润",
            "client_expenses": "招待费",
            "general_expenses": "管理费用",
            "net_profit": "净利润",
        },
        "by_client": ["客户", "收入", "已付", "成本", "直接费用", "招待费", "净利润", "欠款"],
        "by_supplier": ["供应商", "采购总额", "已付", "欠款", "数量", "逾期"],
        "expenses": ["类别", "金额CNY", "%", "数量"],
        "tonnage": {
            "summary": ["重量(kg)", "体积(m³)", "订单数"],
            "by_warehouse": ["仓库", "订单数", "重量(kg)", "体积(m³)"],
            "by_month": ["年", "月", "重量(kg)", "体积(m³)"],
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
        (h["cogs"], data.get("cogs"), prev.get("cogs"), None),
        (h["direct_expenses"], data.get("direct_expenses"), prev.get("direct_expenses"), None),
        (h["gross_profit"], data.get("gross_profit"), prev.get("gross_profit"), data.get("pct_gross_profit")),
        (h["client_expenses"], data.get("client_expenses"), prev.get("client_expenses"), None),
        (h["general_expenses"], data.get("general_expenses"), prev.get("general_expenses"), None),
        (h["net_profit"], data.get("net_profit"), prev.get("net_profit"), data.get("pct_net_profit")),
    ]
    profit_rows = {h["gross_profit"], h["net_profit"]}

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

    totals = {k: Decimal("0") for k in ["revenue", "paid", "cogs", "direct_expenses", "client_expenses", "net_profit", "debt"]}
    for i, row in enumerate(data):
        ws.append([
            row.get("client_name"),
            _fmt(row.get("revenue")),
            _fmt(row.get("paid")),
            _fmt(row.get("cogs")),
            _fmt(row.get("direct_expenses")),
            _fmt(row.get("client_expenses")),
            _fmt(row.get("net_profit")),
            _fmt(row.get("debt")),
        ])
        for k in totals:
            totals[k] += row.get(k, Decimal("0")) or Decimal("0")
        if i % 2 == 1:
            for col in range(1, 9):
                ws.cell(row=ws.max_row, column=col).fill = ALT_FILL

    # Summary row
    ws.append(["Итого" if lang == "ru" else "合计",
               _fmt(totals["revenue"]), _fmt(totals["paid"]), _fmt(totals["cogs"]),
               _fmt(totals["direct_expenses"]), _fmt(totals["client_expenses"]),
               _fmt(totals["net_profit"]), _fmt(totals["debt"])])
    for col in range(1, 9):
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
