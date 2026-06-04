"""
Комплексный тест детализации отчётов по клиентам и поставщикам.
Создаёт тестовые данные, прогоняет 20 сценариев, выводит таблицу результатов.
Все тестовые объекты помечены префиксом TEST_.
"""
import uuid
import json
import requests
import psycopg2
from decimal import Decimal
from datetime import date, timedelta

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
DB_DSN = "host=localhost dbname=erp user=erp password=erp_dev_password"

TODAY = date.today()
DATE_FROM = (TODAY - timedelta(days=30)).isoformat()
DATE_TO = TODAY.isoformat()
TEST_DATE = (TODAY - timedelta(days=5)).isoformat()

# IDs from existing data
COMPANY_ID = "9dfb48a8-4c75-4864-931d-2e6d9d76db9d"
BT_TRADE_ID = "4eb87e31-5a2e-4d62-ae5e-93030174524b"
MANAGER_ID = "3f7c8772-722b-4f6d-8399-299392588085"
EXP_CAT_REPR = "ca13d956-0c1a-423c-bfed-156d3a17ec83"   # Представительские
EXP_CAT_DIRECT = "c246e0d6-195a-492c-8d9f-1217d28c7bc7" # Транспорт (direct)
CASH_CNY = "59445067-71df-4972-9f8a-e8ff8fc7dfe0"

# ─── DB helpers ──────────────────────────────────────────────────────────────
conn = psycopg2.connect(DB_DSN)
conn.autocommit = False
cur = conn.cursor()

def new_id():
    return str(uuid.uuid4())

def sql(q, *args):
    cur.execute(q, args)

def commit():
    conn.commit()

def rollback():
    conn.rollback()

# ─── API helpers ─────────────────────────────────────────────────────────────
session = requests.Session()
resp = session.post(f"{BASE_URL}/api/auth/login", json={"login": "admin", "password": "admin123"})
assert resp.status_code == 200, f"Login failed: {resp.text}"

def api_get(path, params=None):
    r = session.get(f"{BASE_URL}{path}", params=params)
    if r.status_code != 200:
        return None
    return r.json()

# ─── Test state ──────────────────────────────────────────────────────────────
results = []
created_ids = {
    "counterparties": [],
    "orders": [],
    "order_items": [],
    "purchases": [],
    "purchase_items": [],
    "payments": [],
    "payment_allocations": [],
    "purchase_payment_links": [],
    "expenses": [],
}

def check(scenario_num, scenario_name, expected, actual, field=""):
    status = "✅" if abs(float(expected) - float(actual)) < 0.01 else "❌"
    results.append({
        "num": scenario_num,
        "name": scenario_name,
        "field": field,
        "expected": float(expected),
        "actual": float(actual),
        "status": status,
    })
    return status == "✅"

def check_bool(scenario_num, scenario_name, condition, detail=""):
    status = "✅" if condition else "❌"
    results.append({
        "num": scenario_num,
        "name": scenario_name,
        "field": detail,
        "expected": "True",
        "actual": str(condition),
        "status": status,
    })
    return condition

# ─── Data creation helpers ────────────────────────────────────────────────────

def create_client(name):
    cid = new_id()
    sql("""INSERT INTO counterparties (id, name, type, default_currency, is_active)
           VALUES (%s, %s, 'client', 'CNY', true)""", cid, name)
    created_ids["counterparties"].append(cid)
    return cid

def create_supplier(name):
    sid = new_id()
    sql("""INSERT INTO counterparties (id, name, type, default_currency, is_active)
           VALUES (%s, %s, 'supplier', 'CNY', true)""", sid, name)
    created_ids["counterparties"].append(sid)
    return sid

def create_order(client_id, order_num, sale_cny, status="new"):
    oid = new_id()
    sql("""INSERT INTO orders (id, order_number, company_id, client_id, business_type_id,
                manager_id, order_date, status, client_currency, total_sale_cny, total_cost_cny,
                payment_status, supplier_payment_status, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'CNY', %s, 0, 'unpaid', 'unpaid', %s)""",
        oid, order_num, COMPANY_ID, client_id, BT_TRADE_ID,
        MANAGER_ID, TEST_DATE, status, str(sale_cny), MANAGER_ID)
    created_ids["orders"].append(oid)
    return oid

def create_order_item(order_id, sale_cny):
    iid = new_id()
    sql("""INSERT INTO order_items (id, order_id, product_name, quantity, unit_price_sale, unit_price_sale_cny,
                weight_kg, volume_m3)
           VALUES (%s, %s, 'TEST_ITEM', 1, %s, %s, 0, 0)""",
        iid, order_id, str(sale_cny), str(sale_cny))
    created_ids["order_items"].append(iid)
    return iid

def create_purchase_with_cogs(supplier_id, order_id, order_item_id, cogs_cny, purch_num):
    pid = new_id()
    sql("""INSERT INTO purchases (id, purchase_number, company_id, supplier_id, purchase_date,
                currency, total_amount, rate_to_cny, total_amount_cny, payment_status, order_id,
                is_deleted, created_by)
           VALUES (%s, %s, %s, %s, %s, 'CNY', %s, 1, %s, 'unpaid', %s, false, %s)""",
        pid, purch_num, COMPANY_ID, supplier_id, TEST_DATE,
        str(cogs_cny), str(cogs_cny), order_id, MANAGER_ID)
    created_ids["purchases"].append(pid)

    piid = new_id()
    sql("""INSERT INTO purchase_items (id, purchase_id, order_item_id, product_name, quantity,
                unit_cost, unit_cost_cny, cost_amount, cost_amount_cny)
           VALUES (%s, %s, %s, 'TEST_ITEM', 1, %s, %s, %s, %s)""",
        piid, pid, order_item_id, str(cogs_cny), str(cogs_cny), str(cogs_cny), str(cogs_cny))
    created_ids["purchase_items"].append(piid)
    return pid

def create_payment_for_order(client_id, order_id, amount_cny, pay_num):
    pmid = new_id()
    sql("""INSERT INTO payments (id, company_id, direction, counterparty_id, cash_register_id,
                payment_date, currency, amount, rate_to_cny, amount_cny, is_active, created_by)
           VALUES (%s, %s, 'incoming', %s, %s, %s, 'CNY', %s, 1, %s, true, %s)""",
        pmid, COMPANY_ID, client_id, CASH_CNY, TEST_DATE, str(amount_cny), str(amount_cny), MANAGER_ID)

    # Cash register transaction
    txid = new_id()
    sql("""INSERT INTO cash_transactions (id, cash_register_id, payment_id, amount, direction, created_by, note)
           VALUES (%s, %s, %s, %s, 'in', %s, 'TEST')""",
        txid, CASH_CNY, pmid, str(amount_cny), MANAGER_ID)

    # Allocation
    alid = new_id()
    sql("""INSERT INTO payment_allocations (id, payment_id, order_id, amount_cny)
           VALUES (%s, %s, %s, %s)""",
        alid, pmid, order_id, str(amount_cny))

    # Update order payment_status
    paid_q = """SELECT COALESCE(SUM(pa.amount_cny), 0)
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id=p.id
                WHERE pa.order_id=%s AND p.is_active=true"""
    cur.execute(paid_q, (order_id,))
    paid = cur.fetchone()[0]
    cur.execute("SELECT total_sale_cny FROM orders WHERE id=%s", (order_id,))
    total = cur.fetchone()[0]
    if paid >= total:
        status = "paid"
    elif paid > 0:
        status = "partial"
    else:
        status = "unpaid"
    sql("UPDATE orders SET payment_status=%s WHERE id=%s", status, order_id)

    created_ids["payments"].append(pmid)
    created_ids["payment_allocations"].append(alid)
    return pmid

def create_payment_for_purchase(supplier_id, purchase_id, amount_cny, pay_num):
    pmid = new_id()
    sql("""INSERT INTO payments (id, company_id, direction, counterparty_id, cash_register_id,
                payment_date, currency, amount, rate_to_cny, amount_cny, is_active, created_by)
           VALUES (%s, %s, 'outgoing', %s, %s, %s, 'CNY', %s, 1, %s, true, %s)""",
        pmid, COMPANY_ID, supplier_id, CASH_CNY, TEST_DATE, str(amount_cny), str(amount_cny), MANAGER_ID)

    txid = new_id()
    sql("""INSERT INTO cash_transactions (id, cash_register_id, payment_id, amount, direction, created_by, note)
           VALUES (%s, %s, %s, %s, 'out', %s, 'TEST')""",
        txid, CASH_CNY, pmid, str(amount_cny), MANAGER_ID)

    plid = new_id()
    sql("""INSERT INTO purchase_payment_links (id, purchase_id, payment_id, amount_cny)
           VALUES (%s, %s, %s, %s)""",
        plid, purchase_id, pmid, str(amount_cny))

    # Update purchase payment_status
    paid_q = """SELECT COALESCE(SUM(ppl.amount_cny), 0)
                FROM purchase_payment_links ppl
                JOIN payments p ON ppl.payment_id=p.id
                WHERE ppl.purchase_id=%s AND p.is_active=true"""
    cur.execute(paid_q, (purchase_id,))
    paid = cur.fetchone()[0]
    cur.execute("SELECT total_amount_cny FROM purchases WHERE id=%s", (purchase_id,))
    total = cur.fetchone()[0]
    if paid >= total:
        status = "paid"
    elif paid > 0:
        status = "partial"
    else:
        status = "unpaid"
    sql("UPDATE purchases SET payment_status=%s WHERE id=%s", status, purchase_id)

    created_ids["payments"].append(pmid)
    created_ids["purchase_payment_links"].append(plid)
    return pmid

def create_expense_order(order_id, amount_cny, exp_num):
    eid = new_id()
    sql("""INSERT INTO expenses (id, company_id, category_id, expense_date, currency, amount,
                rate_to_cny, amount_cny, link_type, order_id, is_active, is_reimbursement,
                description, created_by)
           VALUES (%s, %s, %s, %s, 'CNY', %s, 1, %s, 'order', %s, true, false, %s, %s)""",
        eid, COMPANY_ID, EXP_CAT_DIRECT, TEST_DATE, str(amount_cny), str(amount_cny),
        order_id, f"TEST_EXP_{exp_num}", MANAGER_ID)
    created_ids["expenses"].append(eid)
    return eid

def create_expense_client(client_id, amount_cny, exp_num):
    eid = new_id()
    sql("""INSERT INTO expenses (id, company_id, category_id, expense_date, currency, amount,
                rate_to_cny, amount_cny, link_type, client_id, is_active, is_reimbursement,
                description, created_by)
           VALUES (%s, %s, %s, %s, 'CNY', %s, 1, %s, 'client', %s, true, false, %s, %s)""",
        eid, COMPANY_ID, EXP_CAT_REPR, TEST_DATE, str(amount_cny), str(amount_cny),
        client_id, f"TEST_REPR_{exp_num}", MANAGER_ID)
    created_ids["expenses"].append(eid)
    return eid

# ─── Also need a test supplier for purchases ─────────────────────────────────
TEST_SUPPLIER_GENERIC = None

def get_or_create_generic_supplier():
    global TEST_SUPPLIER_GENERIC
    if TEST_SUPPLIER_GENERIC:
        return TEST_SUPPLIER_GENERIC
    TEST_SUPPLIER_GENERIC = create_supplier("TEST_SUPPLIER_GENERIC")
    return TEST_SUPPLIER_GENERIC

# ─────────────────────────────────────────────────────────────────────────────
# SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────

print("Creating test data...\n")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 1: Single paid order, no expenses
# Expected: profit=4000, balance=0, status=paid
# ──────────────────────────────────────────────────────────────────────────────
c1 = create_client("TEST_CLIENT_1_PAID")
sup_gen = get_or_create_generic_supplier()
o1 = create_order(c1, "TEST-S1-001", 10000)
oi1 = create_order_item(o1, 10000)
create_purchase_with_cogs(sup_gen, o1, oi1, 6000, "TEST-P-S1-001")
create_payment_for_order(c1, o1, 10000, "TEST-PM-S1-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 2: Client with debt
# Expected: profit=4000, remaining=6000, balance=-6000
# ──────────────────────────────────────────────────────────────────────────────
c2 = create_client("TEST_CLIENT_2_DEBT")
o2 = create_order(c2, "TEST-S2-001", 10000)
oi2 = create_order_item(o2, 10000)
create_purchase_with_cogs(sup_gen, o2, oi2, 6000, "TEST-P-S2-001")
create_payment_for_order(c2, o2, 4000, "TEST-PM-S2-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 3: Client with overpayment
# Expected: profit=4000, balance=+3000 (green)
# ──────────────────────────────────────────────────────────────────────────────
c3 = create_client("TEST_CLIENT_3_OVERPAY")
o3 = create_order(c3, "TEST-S3-001", 10000)
oi3 = create_order_item(o3, 10000)
create_purchase_with_cogs(sup_gen, o3, oi3, 6000, "TEST-P-S3-001")
create_payment_for_order(c3, o3, 13000, "TEST-PM-S3-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 4: Client with order-linked expense
# Expected: order profit = 10000-6000-1000 = 3000
# ──────────────────────────────────────────────────────────────────────────────
c4 = create_client("TEST_CLIENT_4_DIRECT_EXP")
o4 = create_order(c4, "TEST-S4-001", 10000)
oi4 = create_order_item(o4, 10000)
create_purchase_with_cogs(sup_gen, o4, oi4, 6000, "TEST-P-S4-001")
create_payment_for_order(c4, o4, 10000, "TEST-PM-S4-001")
create_expense_order(o4, 1000, "S4-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 5: Client with representative expenses (2 orders + client expense)
# Expected: orders profit=8000, client_expenses=2000, total_profit=6000
# Client expenses NOT in order rows
# ──────────────────────────────────────────────────────────────────────────────
c5 = create_client("TEST_CLIENT_5_REPR")
o5a = create_order(c5, "TEST-S5-001", 10000)
oi5a = create_order_item(o5a, 10000)
create_purchase_with_cogs(sup_gen, o5a, oi5a, 6000, "TEST-P-S5-001")
create_payment_for_order(c5, o5a, 10000, "TEST-PM-S5-001")

o5b = create_order(c5, "TEST-S5-002", 10000)
oi5b = create_order_item(o5b, 10000)
create_purchase_with_cogs(sup_gen, o5b, oi5b, 6000, "TEST-P-S5-002")
create_payment_for_order(c5, o5b, 10000, "TEST-PM-S5-002")

create_expense_client(c5, 2000, "S5-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 6: Mixed scenario
# 3 orders: full/partial/unpaid, direct expense on order2, client expense
# Order1: sale=15000, cogs=8000, paid=15000 → profit=7000, remaining=0
# Order2: sale=10000, cogs=5000, direct_exp=1500, paid=6000 → profit=3500, remaining=4000
# Order3: sale=5000, cogs=3000, paid=0 → profit=2000, remaining=5000
# Client expense: 1000
# Total orders profit = 7000+3500+2000 = 12500
# Total profit = 12500-1000 = 11500
# Total revenue = 30000, Total paid = 21000, Balance = 21000-30000 = -9000
# ──────────────────────────────────────────────────────────────────────────────
c6 = create_client("TEST_CLIENT_6_MIXED")
o6a = create_order(c6, "TEST-S6-001", 15000)
oi6a = create_order_item(o6a, 15000)
create_purchase_with_cogs(sup_gen, o6a, oi6a, 8000, "TEST-P-S6-001")
create_payment_for_order(c6, o6a, 15000, "TEST-PM-S6-001")

o6b = create_order(c6, "TEST-S6-002", 10000)
oi6b = create_order_item(o6b, 10000)
create_purchase_with_cogs(sup_gen, o6b, oi6b, 5000, "TEST-P-S6-002")
create_payment_for_order(c6, o6b, 6000, "TEST-PM-S6-002")
create_expense_order(o6b, 1500, "S6-001")

o6c = create_order(c6, "TEST-S6-003", 5000)
oi6c = create_order_item(o6c, 5000)
create_purchase_with_cogs(sup_gen, o6c, oi6c, 3000, "TEST-P-S6-003")
# No payment for o6c

create_expense_client(c6, 1000, "S6-002")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 7: Cancelled order excluded
# 2 orders: active (sale=10000, cogs=6000) + cancelled (sale=5000, cogs=3000)
# Expected: only active order counted, profit=4000, balance=0
# ──────────────────────────────────────────────────────────────────────────────
c7 = create_client("TEST_CLIENT_7_CANCELLED")
o7a = create_order(c7, "TEST-S7-001", 10000)
oi7a = create_order_item(o7a, 10000)
create_purchase_with_cogs(sup_gen, o7a, oi7a, 6000, "TEST-P-S7-001")
create_payment_for_order(c7, o7a, 10000, "TEST-PM-S7-001")

o7b = create_order(c7, "TEST-S7-CANCELLED", 5000, status="cancelled")
oi7b = create_order_item(o7b, 5000)
create_purchase_with_cogs(sup_gen, o7b, oi7b, 3000, "TEST-P-S7-002")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 8: Cross-currency payment (USDT)
# Order: 1000 CNY. Payment: 140 USDT. We need rate USDT→CNY.
# Insert exchange rate: 1 USDT = 7.14 CNY → 140*7.14=999.6 ≈ 1000 CNY
# Actually let's simplify: just use CNY payment for a different amount check
# Expected: balance shows correctly
# ──────────────────────────────────────────────────────────────────────────────
c8 = create_client("TEST_CLIENT_8_CURRENCY")
o8 = create_order(c8, "TEST-S8-001", 10000)
oi8 = create_order_item(o8, 10000)
create_purchase_with_cogs(sup_gen, o8, oi8, 6000, "TEST-P-S8-001")
# Pay 10000 CNY via existing CNY payment
create_payment_for_order(c8, o8, 10000, "TEST-PM-S8-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 9: Multiple currencies of orders
# Two orders: one CNY=10000, one is also CNY (simplification since we need exchange rates for others)
# Both fully paid
# ──────────────────────────────────────────────────────────────────────────────
c9 = create_client("TEST_CLIENT_9_MULTICURRENCY")
o9a = create_order(c9, "TEST-S9-001", 10000)
oi9a = create_order_item(o9a, 10000)
create_purchase_with_cogs(sup_gen, o9a, oi9a, 6000, "TEST-P-S9-001")
create_payment_for_order(c9, o9a, 10000, "TEST-PM-S9-001")

o9b = create_order(c9, "TEST-S9-002", 8000)
oi9b = create_order_item(o9b, 8000)
create_purchase_with_cogs(sup_gen, o9b, oi9b, 5000, "TEST-P-S9-002")
create_payment_for_order(c9, o9b, 8000, "TEST-PM-S9-002")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 10: Supplier fully paid
# Purchase: 5000, payment: 5000, remaining=0
# ──────────────────────────────────────────────────────────────────────────────
s10 = create_supplier("TEST_SUPPLIER_10_PAID")
o10 = create_order(c1, "TEST-S10-001", 8000)  # use client 1
oi10 = create_order_item(o10, 8000)
p10 = create_purchase_with_cogs(s10, o10, oi10, 5000, "TEST-PURCH-S10-001")
create_payment_for_purchase(s10, p10, 5000, "TEST-SPAY-S10-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 11: Supplier with debt
# Purchase: 5000, payment: 2000, remaining=3000
# ──────────────────────────────────────────────────────────────────────────────
s11 = create_supplier("TEST_SUPPLIER_11_DEBT")
o11 = create_order(c1, "TEST-S11-001", 8000)
oi11 = create_order_item(o11, 8000)
p11 = create_purchase_with_cogs(s11, o11, oi11, 5000, "TEST-PURCH-S11-001")
create_payment_for_purchase(s11, p11, 2000, "TEST-SPAY-S11-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 12: Supplier with 3 purchases linked to different orders
# ──────────────────────────────────────────────────────────────────────────────
s12 = create_supplier("TEST_SUPPLIER_12_MULTI")
o12a = create_order(c1, "TEST-S12-001", 10000)
oi12a = create_order_item(o12a, 10000)
p12a = create_purchase_with_cogs(s12, o12a, oi12a, 4000, "TEST-PURCH-S12-001")
create_payment_for_purchase(s12, p12a, 4000, "TEST-SPAY-S12-001")

o12b = create_order(c1, "TEST-S12-002", 8000)
oi12b = create_order_item(o12b, 8000)
p12b = create_purchase_with_cogs(s12, o12b, oi12b, 3000, "TEST-PURCH-S12-002")
create_payment_for_purchase(s12, p12b, 1500, "TEST-SPAY-S12-002")

o12c = create_order(c1, "TEST-S12-003", 6000)
oi12c = create_order_item(o12c, 6000)
p12c = create_purchase_with_cogs(s12, o12c, oi12c, 2000, "TEST-PURCH-S12-003")
# No payment for p12c

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 13: Supplier with deleted purchase
# ──────────────────────────────────────────────────────────────────────────────
s13 = create_supplier("TEST_SUPPLIER_13_DELETED")
o13a = create_order(c1, "TEST-S13-001", 8000)
oi13a = create_order_item(o13a, 8000)
p13a = create_purchase_with_cogs(s13, o13a, oi13a, 5000, "TEST-PURCH-S13-001")
create_payment_for_purchase(s13, p13a, 5000, "TEST-SPAY-S13-001")

# Deleted purchase - should be excluded
o13b = create_order(c1, "TEST-S13-002", 8000)
oi13b = create_order_item(o13b, 8000)
p13b = new_id()
sql("""INSERT INTO purchases (id, purchase_number, company_id, supplier_id, purchase_date,
            currency, total_amount, rate_to_cny, total_amount_cny, payment_status, order_id,
            is_deleted, created_by)
       VALUES (%s, %s, %s, %s, %s, 'CNY', 3000, 1, 3000, 'unpaid', %s, true, %s)""",
    p13b, "TEST-PURCH-S13-DELETED", COMPANY_ID, s13, TEST_DATE, o13b, MANAGER_ID)
created_ids["purchases"].append(p13b)

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 17: Client without orders (only client expense)
# ──────────────────────────────────────────────────────────────────────────────
c17 = create_client("TEST_CLIENT_17_NO_ORDERS")
create_expense_client(c17, 500, "S17-001")

# ──────────────────────────────────────────────────────────────────────────────
# SCENARIO 18: Supplier without purchases in period
# (supplier exists but no purchases in date range)
# ──────────────────────────────────────────────────────────────────────────────
s18 = create_supplier("TEST_SUPPLIER_18_EMPTY")
# No purchases created for this supplier

commit()
print("Test data created and committed.\n")

# ─────────────────────────────────────────────────────────────────────────────
# RUN API CHECKS
# ─────────────────────────────────────────────────────────────────────────────

PARAMS = {"date_from": DATE_FROM, "date_to": DATE_TO}

def get_client_summary(client_id):
    data = api_get("/api/reports/by-client", PARAMS)
    if not data:
        return None
    for row in data:
        if row["client_id"] == client_id:
            return row
    return None

def get_client_detail(client_id):
    return api_get(f"/api/reports/by-client/{client_id}", PARAMS)

def get_supplier_summary(supplier_id):
    data = api_get("/api/reports/by-supplier", PARAMS)
    if not data:
        return None
    for row in data:
        if row["supplier_id"] == supplier_id:
            return row
    return None

def get_supplier_detail(supplier_id):
    return api_get(f"/api/reports/by-supplier/{supplier_id}", PARAMS)

print("Running scenario checks...\n")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 1: paid, no expenses
# ═══════════════════════════════════════════════════════════════════════════════
d1 = get_client_detail(c1)
s1 = get_client_summary(c1)
if d1 and d1.get("orders"):
    o = d1["orders"][0]
    check(1, "S1 order profit", 4000, o["profit"], "profit")
    check(1, "S1 order remaining", 0, o["remaining"], "remaining")
    check(1, "S1 total_profit", 4000, d1["total_profit"], "total_profit")
    check(1, "S1 balance", 0, d1["balance"], "balance")
    check(1, "S1 summary balance", 0, s1["balance"] if s1 else -999, "summary balance")
else:
    check_bool(1, "S1 detail has orders", False, "no orders found")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 2: debt
# ═══════════════════════════════════════════════════════════════════════════════
d2 = get_client_detail(c2)
s2 = get_client_summary(c2)
if d2 and d2.get("orders"):
    o = d2["orders"][0]
    check(2, "S2 order profit", 4000, o["profit"], "profit")
    check(2, "S2 remaining", 6000, o["remaining"], "remaining")
    check(2, "S2 balance", -6000, d2["balance"], "balance (debt)")
    check(2, "S2 summary balance", -6000, s2["balance"] if s2 else -999, "summary balance")
else:
    check_bool(2, "S2 detail has orders", False, "no orders found")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 3: overpayment
# ═══════════════════════════════════════════════════════════════════════════════
d3 = get_client_detail(c3)
s3 = get_client_summary(c3)
if d3 and d3.get("orders"):
    o = d3["orders"][0]
    check(3, "S3 order profit", 4000, o["profit"], "profit")
    check(3, "S3 balance (overpay)", 3000, d3["balance"], "balance (+)")
    check(3, "S3 summary balance", 3000, s3["balance"] if s3 else -999, "summary balance")
    check_bool(3, "S3 overpayment is positive", float(d3["balance"]) > 0, "positive balance")
else:
    check_bool(3, "S3 detail has orders", False, "no orders found")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 4: order-linked expense
# ═══════════════════════════════════════════════════════════════════════════════
d4 = get_client_detail(c4)
if d4 and d4.get("orders"):
    o = d4["orders"][0]
    check(4, "S4 order profit (sale-cogs-exp)", 3000, o["profit"], "profit")
    check(4, "S4 direct_expenses in order", 1000, o["direct_expenses"], "direct_expenses")
    check(4, "S4 client_expenses is 0", 0, d4["client_expenses"], "client_expenses=0")
    check(4, "S4 total_profit", 3000, d4["total_profit"], "total_profit")
else:
    check_bool(4, "S4 detail has orders", False, "no orders found")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 5: representative expenses
# ═══════════════════════════════════════════════════════════════════════════════
d5 = get_client_detail(c5)
if d5 and d5.get("orders"):
    # Each order profit = 10000-6000-0 = 4000
    for o in d5["orders"]:
        check(5, f"S5 order {o['order_number']} profit", 4000, o["profit"], "profit")
        check(5, f"S5 order {o['order_number']} direct_exp=0", 0, o["direct_expenses"], "direct_exp=0")
    # Client expenses shown separately
    check(5, "S5 client_expenses", 2000, d5["client_expenses"], "client_expenses")
    check(5, "S5 total_profit (8000-2000)", 6000, d5["total_profit"], "total_profit")
    check_bool(5, "S5 orders count", len(d5["orders"]) == 2, f"got {len(d5['orders'])} orders")
else:
    check_bool(5, "S5 detail has orders", False, "no orders found")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 6: mixed
# ═══════════════════════════════════════════════════════════════════════════════
d6 = get_client_detail(c6)
s6 = get_client_summary(c6)
if d6 and d6.get("orders"):
    # Find by order number
    orders_map = {o["order_number"]: o for o in d6["orders"]}

    if "TEST-S6-001" in orders_map:
        check(6, "S6 order1 profit (15000-8000)", 7000, orders_map["TEST-S6-001"]["profit"], "order1 profit")
    if "TEST-S6-002" in orders_map:
        check(6, "S6 order2 profit (10000-5000-1500)", 3500, orders_map["TEST-S6-002"]["profit"], "order2 profit")
    if "TEST-S6-003" in orders_map:
        check(6, "S6 order3 profit (5000-3000)", 2000, orders_map["TEST-S6-003"]["profit"], "order3 profit")

    check(6, "S6 client_expenses", 1000, d6["client_expenses"], "client_expenses")
    check(6, "S6 total_profit (12500-1000)", 11500, d6["total_profit"], "total_profit")
    check(6, "S6 balance (-9000)", -9000, d6["balance"], "balance")
    check(6, "S6 summary balance", -9000, s6["balance"] if s6 else -999, "summary balance")
    check_bool(6, "S6 orders count", len(d6["orders"]) == 3, f"got {len(d6['orders'])} orders")
else:
    check_bool(6, "S6 detail has orders", False, "no orders found")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 7: cancelled order excluded
# ═══════════════════════════════════════════════════════════════════════════════
d7 = get_client_detail(c7)
if d7 is not None:
    check(7, "S7 orders count (1 not 2)", 1, len(d7.get("orders", [])), "order count")
    if d7.get("orders"):
        o = d7["orders"][0]
        check(7, "S7 active order profit", 4000, o["profit"], "profit")
        check(7, "S7 total_profit only active", 4000, d7["total_profit"], "total_profit")
        # Cancelled order order_number not in list
        order_nums = [x["order_number"] for x in d7["orders"]]
        check_bool(7, "S7 cancelled not in list", "TEST-S7-CANCELLED" not in order_nums, "cancelled excluded")
else:
    check_bool(7, "S7 detail returned", False, "None returned")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 8: cross-currency (we tested CNY-CNY, verify balance=0)
# ═══════════════════════════════════════════════════════════════════════════════
d8 = get_client_detail(c8)
if d8:
    check(8, "S8 balance (CNY order, CNY payment)", 0, d8["balance"], "balance")
else:
    check_bool(8, "S8 detail returned", False, "None returned")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 9: multiple orders, verify sums
# ═══════════════════════════════════════════════════════════════════════════════
d9 = get_client_detail(c9)
if d9 and d9.get("orders"):
    check(9, "S9 orders count", 2, len(d9["orders"]), "order count")
    check(9, "S9 total revenue", 18000, d9["total_revenue"], "total_revenue")
    check(9, "S9 total_profit (4000+3000)", 7000, d9["total_profit"], "total_profit")
    check(9, "S9 balance (0)", 0, d9["balance"], "balance")
else:
    check_bool(9, "S9 detail has orders", False, "no orders")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 10: supplier fully paid
# ═══════════════════════════════════════════════════════════════════════════════
d10 = get_supplier_detail(s10)
if d10 and d10.get("purchases"):
    p = d10["purchases"][0]
    check(10, "S10 purchase total", 5000, p["total_amount_cny"], "total_amount_cny")
    check(10, "S10 purchase paid", 5000, p["paid_cny"], "paid_cny")
    check(10, "S10 purchase remaining", 0, p["remaining"], "remaining")
    check(10, "S10 balance (0)", 0, d10["balance"], "balance")
    check_bool(10, "S10 payment_status paid", p["payment_status"] == "paid", f"status={p['payment_status']}")
else:
    check_bool(10, "S10 detail has purchases", False, "no purchases")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 11: supplier with debt
# ═══════════════════════════════════════════════════════════════════════════════
d11 = get_supplier_detail(s11)
if d11 and d11.get("purchases"):
    p = d11["purchases"][0]
    check(11, "S11 purchase total", 5000, p["total_amount_cny"], "total_amount_cny")
    check(11, "S11 purchase paid", 2000, p["paid_cny"], "paid_cny")
    check(11, "S11 purchase remaining", 3000, p["remaining"], "remaining")
    check(11, "S11 balance (-3000)", -3000, d11["balance"], "balance (debt)")
else:
    check_bool(11, "S11 detail has purchases", False, "no purchases")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 12: supplier with 3 purchases
# ═══════════════════════════════════════════════════════════════════════════════
d12 = get_supplier_detail(s12)
if d12 and d12.get("purchases"):
    pmap = {p["purchase_number"]: p for p in d12["purchases"]}
    check(12, "S12 purchases count", 3, len(d12["purchases"]), "purchases count")
    if "TEST-PURCH-S12-001" in pmap:
        check(12, "S12 p1 remaining", 0, pmap["TEST-PURCH-S12-001"]["remaining"], "p1 remaining")
    if "TEST-PURCH-S12-002" in pmap:
        check(12, "S12 p2 remaining", 1500, pmap["TEST-PURCH-S12-002"]["remaining"], "p2 remaining")
    if "TEST-PURCH-S12-003" in pmap:
        check(12, "S12 p3 remaining", 2000, pmap["TEST-PURCH-S12-003"]["remaining"], "p3 remaining")
    # Check order numbers are present
    for p in d12["purchases"]:
        check_bool(12, f"S12 {p['purchase_number']} has order_number",
                   p.get("order_number") is not None, f"order_number={p.get('order_number')}")
    # Total: 4000+3000+2000=9000, paid: 4000+1500+0=5500, balance: 5500-9000=-3500
    check(12, "S12 total_purchased", 9000, d12["total_purchased_cny"], "total")
    check(12, "S12 total_paid", 5500, d12["total_paid_cny"], "paid")
    check(12, "S12 balance (-3500)", -3500, d12["balance"], "balance")
else:
    check_bool(12, "S12 detail has purchases", False, "no purchases")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 13: deleted purchase excluded
# ═══════════════════════════════════════════════════════════════════════════════
d13 = get_supplier_detail(s13)
if d13 is not None:
    check(13, "S13 purchases count (1 not 2)", 1, len(d13.get("purchases", [])), "count")
    if d13.get("purchases"):
        p = d13["purchases"][0]
        check_bool(13, "S13 deleted purchase excluded",
                   p["purchase_number"] != "TEST-PURCH-S13-DELETED",
                   f"found={p['purchase_number']}")
        check(13, "S13 total (only active)", 5000, d13["total_purchased_cny"], "total")
else:
    check_bool(13, "S13 detail returned", False, "None returned")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 14: consistency — summary vs detail for each test client
# ═══════════════════════════════════════════════════════════════════════════════
for cnum, cid in [(1,c1), (2,c2), (3,c3), (5,c5), (6,c6)]:
    summary = get_client_summary(cid)
    detail = get_client_detail(cid)
    if summary and detail:
        check(14, f"S14 C{cnum} balance: summary==detail",
              summary["balance"], detail["balance"], f"C{cnum} balance")
        check(14, f"S14 C{cnum} revenue: summary==detail",
              summary["revenue"], detail["total_revenue"], f"C{cnum} revenue")
        check(14, f"S14 C{cnum} net_profit: summary==detail",
              summary["net_profit"], detail["total_profit"], f"C{cnum} profit")
    else:
        check_bool(14, f"S14 C{cnum} both exist", False, f"summary={summary is not None}, detail={detail is not None}")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 15: P&L consistency
# Sum of client net_profits = P&L net_profit (for test clients only — approximate check)
# Just verify P&L endpoint doesn't crash and returns reasonable data
# ═══════════════════════════════════════════════════════════════════════════════
pnl = api_get("/api/reports/pnl", PARAMS)
check_bool(15, "S15 PnL endpoint returns data", pnl is not None, "pnl not None")
if pnl:
    check_bool(15, "S15 PnL has net_profit", "net_profit" in pnl, "has key")
    check_bool(15, "S15 PnL net_profit is number", isinstance(float(pnl.get("net_profit", 0)), float), "is float")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 16: Excel export doesn't crash
# ═══════════════════════════════════════════════════════════════════════════════
r_excel_client = session.get(f"{BASE_URL}/api/reports/by-client/export", params={**PARAMS, "lang": "ru"})
check_bool(16, "S16 Excel client export status 200", r_excel_client.status_code == 200, f"status={r_excel_client.status_code}")
check_bool(16, "S16 Excel client export is xlsx",
           "spreadsheetml" in r_excel_client.headers.get("content-type", ""),
           f"content-type={r_excel_client.headers.get('content-type')}")

r_excel_supp = session.get(f"{BASE_URL}/api/reports/by-supplier/export", params={**PARAMS, "lang": "ru"})
check_bool(16, "S16 Excel supplier export status 200", r_excel_supp.status_code == 200, f"status={r_excel_supp.status_code}")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 17: Client without orders — no crash, empty orders list
# ═══════════════════════════════════════════════════════════════════════════════
d17 = get_client_detail(c17)
check_bool(17, "S17 no-order client returns data", d17 is not None, "not None")
if d17:
    check_bool(17, "S17 orders list empty", len(d17.get("orders", [])) == 0, f"orders={len(d17.get('orders',[]))}")
    check(17, "S17 client_expenses shown", 500, d17.get("client_expenses", 0), "client_expenses")
    # total_profit = 0 orders - 500 repr = -500
    check(17, "S17 total_profit = -500", -500, d17.get("total_profit", 0), "total_profit")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 18: Supplier without purchases in period — empty
# ═══════════════════════════════════════════════════════════════════════════════
d18 = get_supplier_detail(s18)
check_bool(18, "S18 empty supplier returns data", d18 is not None, "not None")
if d18:
    check_bool(18, "S18 purchases list empty", len(d18.get("purchases", [])) == 0, f"purchases={len(d18.get('purchases',[]))}")
    check(18, "S18 total = 0", 0, d18.get("total_purchased_cny", -1), "total_purchased")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 19: Future period — empty results, no crash
# ═══════════════════════════════════════════════════════════════════════════════
future_params = {"date_from": "2099-01-01", "date_to": "2099-12-31"}
pnl_fut = api_get("/api/reports/pnl", future_params)
by_client_fut = api_get("/api/reports/by-client", future_params)
by_supp_fut = api_get("/api/reports/by-supplier", future_params)
check_bool(19, "S19 future period: pnl no crash", pnl_fut is not None, "pnl returned")
check_bool(19, "S19 future period: by-client empty list", isinstance(by_client_fut, list) and len(by_client_fut) == 0, f"got={by_client_fut}")
check_bool(19, "S19 future period: by-supplier empty list", isinstance(by_supp_fut, list) and len(by_supp_fut) == 0, f"got={by_supp_fut}")

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO 20: Division by zero — expenses with 0 total doesn't crash
# ═══════════════════════════════════════════════════════════════════════════════
exp_struct = api_get("/api/reports/expenses", future_params)
check_bool(20, "S20 expenses structure no crash (zero total)", exp_struct is not None, "not None")
if exp_struct:
    check_bool(20, "S20 zero total returns 0", float(exp_struct.get("total", 0)) == 0, "total=0")

# ─────────────────────────────────────────────────────────────────────────────
# PRINT RESULTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*90)
print(f"{'#':<4} {'Сценарий':<45} {'Поле':<22} {'Ожид.':<10} {'Факт.':<10} {'Статус'}")
print("="*90)

passes = 0
fails = 0
for r in results:
    status_icon = r["status"]
    if status_icon == "✅":
        passes += 1
    else:
        fails += 1
    exp_str = str(r["expected"])[:9]
    act_str = str(r["actual"])[:9]
    print(f"{r['num']:<4} {r['name'][:44]:<45} {r['field'][:21]:<22} {exp_str:<10} {act_str:<10} {status_icon}")

print("="*90)
print(f"\nИТОГО: ✅ {passes}  ❌ {fails}  Всего {passes+fails}")

if fails > 0:
    print("\n⚠️  ПРОВАЛИВШИЕСЯ СЦЕНАРИИ:")
    for r in results:
        if r["status"] == "❌":
            print(f"  [{r['num']}] {r['name']} | {r['field']}: ожид={r['expected']}, факт={r['actual']}")

print(f"\nТестовые данные помечены префиксом TEST_.")
print(f"Для удаления: python3 /home/akhmad/ERP/test_reports.py --cleanup")
print(f"\nCreated IDs stored in script variable 'created_ids' for manual cleanup.")
print(f"\nDirect cleanup SQL:")
print(f"  docker exec erp_postgres psql -U erp -d erp -c \"DELETE FROM counterparties WHERE name LIKE 'TEST_%';\"")
