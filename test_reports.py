"""
Тест детализации отчётов. Запускать: python3 test_reports.py
Тестовые данные: все с префиксом TEST_
Удаление: python3 test_reports.py --cleanup
"""
import sys, uuid, requests, psycopg2
from datetime import date, timedelta

BASE_URL = "http://localhost:8000"
DB_DSN   = "host=localhost dbname=erp user=erp password=erp_dev_password"
TODAY    = date.today()
DATE_FROM = (TODAY - timedelta(days=30)).isoformat()
DATE_TO   = TODAY.isoformat()
TEST_DATE = (TODAY - timedelta(days=5)).isoformat()

COMPANY_ID     = "9dfb48a8-4c75-4864-931d-2e6d9d76db9d"
BT_TRADE_ID    = "4eb87e31-5a2e-4d62-ae5e-93030174524b"
MANAGER_ID     = "3f7c8772-722b-4f6d-8399-299392588085"
EXP_REPR       = "ca13d956-0c1a-423c-bfed-156d3a17ec83"
EXP_DIRECT     = "c246e0d6-195a-492c-8d9f-1217d28c7bc7"

# ─── DB ───────────────────────────────────────────────────────────────────────
db = psycopg2.connect(DB_DSN)
db.autocommit = True
c = db.cursor()
def run(sql, *a): c.execute(sql, a)
def one(sql, *a):
    c.execute(sql, a); r = c.fetchone(); return str(r[0]) if r else None
def uid(): return str(uuid.uuid4())

# ─── Cleanup mode ─────────────────────────────────────────────────────────────
if "--cleanup" in sys.argv:
    print("Удаление тестовых данных...")
    c.execute("""
        DO $$ DECLARE
          cp_ids uuid[]; ord_ids uuid[]; pur_ids uuid[];
        BEGIN
          SELECT array_agg(id) INTO cp_ids  FROM counterparties WHERE name LIKE 'TEST_%';
          SELECT array_agg(id) INTO ord_ids FROM orders           WHERE order_number LIKE 'TEST-%';
          SELECT array_agg(id) INTO pur_ids FROM purchases        WHERE purchase_number LIKE 'TEST-%';
          DELETE FROM expenses              WHERE description LIKE 'TEST_%' OR order_id=ANY(ord_ids) OR client_id=ANY(cp_ids);
          DELETE FROM purchase_payments_link WHERE purchase_id=ANY(pur_ids);
          DELETE FROM payment_allocations   WHERE order_id=ANY(ord_ids);
          DELETE FROM payments              WHERE counterparty_id=ANY(cp_ids);
          DELETE FROM purchase_items        WHERE purchase_id=ANY(pur_ids);
          DELETE FROM purchases             WHERE purchase_number LIKE 'TEST-%';
          DELETE FROM order_items           WHERE order_id=ANY(ord_ids);
          DELETE FROM orders                WHERE order_number LIKE 'TEST-%';
          DELETE FROM counterparties        WHERE name LIKE 'TEST_%';
        END $$;
    """)
    print("Готово.")
    sys.exit(0)

# ─── API ──────────────────────────────────────────────────────────────────────
sess = requests.Session()
r = sess.post(f"{BASE_URL}/api/auth/login", json={"login":"admin","password":"admin123"})
assert r.status_code == 200, f"Login failed: {r.text}"

PARAMS = {"date_from": DATE_FROM, "date_to": DATE_TO}

def api(path, params=None):
    r = sess.get(f"{BASE_URL}{path}", params=params or PARAMS)
    if r.status_code != 200:
        print(f"  WARN {path} → {r.status_code}")
        return None
    return r.json()

def csum(cid): return next((x for x in (api("/api/reports/by-client") or []) if x["client_id"]==cid), None)
def cdet(cid): return api(f"/api/reports/by-client/{cid}")
def ssum(sid): return next((x for x in (api("/api/reports/by-supplier") or []) if x["supplier_id"]==sid), None)
def sdet(sid): return api(f"/api/reports/by-supplier/{sid}")

# ─── Results ──────────────────────────────────────────────────────────────────
results = []
def chk(num, name, exp, got, field=""):
    ok = abs(float(exp)-float(got)) < 0.02
    results.append({"num":num,"name":name,"field":field,"exp":float(exp),"got":float(got),"ok":ok})
    return ok
def chk_b(num, name, cond, detail=""):
    results.append({"num":num,"name":name,"field":detail,"exp":"T","got":str(cond),"ok":cond})
    return cond

# ─── DB creation helpers ──────────────────────────────────────────────────────
def _cp(name, tp):
    r = one("SELECT id FROM counterparties WHERE name=%s", name)
    if r: return r
    nid = uid()
    run("INSERT INTO counterparties (id,name,type,default_currency,is_active) VALUES (%s,%s,%s,'CNY',true)", nid, name, tp)
    return nid

def mk_cl(name):  return _cp(name, "client")
def mk_su(name):  return _cp(name, "supplier")

def mk_ord(cid, num, sale, status="new"):
    r = one("SELECT id FROM orders WHERE order_number=%s", num)
    if r: return r
    nid = uid()
    run("""INSERT INTO orders (id,order_number,company_id,client_id,business_type_id,manager_id,
             order_date,status,client_currency,total_sale_cny,total_cost_cny,
             payment_status,supplier_payment_status,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'CNY',%s,0,'unpaid','unpaid',%s)""",
        nid, num, COMPANY_ID, cid, BT_TRADE_ID, MANAGER_ID, TEST_DATE, status, str(sale), MANAGER_ID)
    return nid

def mk_oi(oid, sale):
    r = one("SELECT id FROM order_items WHERE order_id=%s LIMIT 1", oid)
    if r: return r
    nid = uid()
    run("INSERT INTO order_items (id,order_id,name,quantity,sale_price,sale_currency,sale_rate_to_cny,weight_kg,volume_m3) VALUES (%s,%s,'TEST_ITEM',1,%s,'CNY',1,0,0)",
        nid, oid, str(sale))
    return nid

def mk_pur(sid, oid, oiid, cogs, pnum):
    r = one("SELECT id FROM purchases WHERE purchase_number=%s", pnum)
    if r: return r
    pid = uid()
    run("""INSERT INTO purchases (id,purchase_number,company_id,supplier_id,purchase_date,
             currency,total_amount,rate_to_cny,total_amount_cny,payment_status,order_id,is_deleted,created_by)
           VALUES (%s,%s,%s,%s,%s,'CNY',%s,1,%s,'unpaid',%s,false,%s)""",
        pid, pnum, COMPANY_ID, sid, TEST_DATE, str(cogs), str(cogs), oid, MANAGER_ID)
    run("INSERT INTO purchase_items (id,purchase_id,order_item_id,quantity,cost_price,cost_amount) VALUES (%s,%s,%s,1,%s,%s)",
        uid(), pid, oiid, str(cogs), str(cogs))
    return pid

def mk_pay_o(cid, oid, amount):
    # Check if payment already allocated to this order
    c.execute("SELECT COUNT(*) FROM payment_allocations WHERE order_id=%s", (oid,))
    if c.fetchone()[0] > 0: return
    pmid = uid()
    run("""INSERT INTO payments (id,company_id,direction,counterparty_id,cash_register_id,
             payment_date,currency,amount,rate_to_cny,amount_cny,is_active,created_by)
           VALUES (%s,%s,'in',%s,(SELECT id FROM cash_registers WHERE currency='CNY' AND is_active=true LIMIT 1),
             %s,'CNY',%s,1,%s,true,%s)""",
        pmid, COMPANY_ID, cid, TEST_DATE, str(amount), str(amount), MANAGER_ID)
    run("INSERT INTO payment_allocations (id,payment_id,order_id,amount_cny) VALUES (%s,%s,%s,%s)",
        uid(), pmid, oid, str(amount))
    c.execute("""SELECT COALESCE(SUM(pa.amount_cny),0) FROM payment_allocations pa
                 JOIN payments p ON pa.payment_id=p.id WHERE pa.order_id=%s AND p.is_active=true""", (oid,))
    paid = float(c.fetchone()[0])
    c.execute("SELECT total_sale_cny FROM orders WHERE id=%s", (oid,))
    tot = float(c.fetchone()[0])
    ps = "paid" if paid >= tot else ("partial" if paid > 0 else "unpaid")
    run("UPDATE orders SET payment_status=%s WHERE id=%s", ps, oid)

def mk_pay_p(sid, pid, amount):
    c.execute("SELECT COUNT(*) FROM purchase_payments_link WHERE purchase_id=%s", (pid,))
    if c.fetchone()[0] > 0: return
    pmid = uid()
    run("""INSERT INTO payments (id,company_id,direction,counterparty_id,cash_register_id,
             payment_date,currency,amount,rate_to_cny,amount_cny,is_active,created_by)
           VALUES (%s,%s,'out',%s,(SELECT id FROM cash_registers WHERE currency='CNY' AND is_active=true LIMIT 1),
             %s,'CNY',%s,1,%s,true,%s)""",
        pmid, COMPANY_ID, sid, TEST_DATE, str(amount), str(amount), MANAGER_ID)
    run("INSERT INTO purchase_payments_link (id,purchase_id,payment_id,amount_cny) VALUES (%s,%s,%s,%s)",
        uid(), pid, pmid, str(amount))
    c.execute("""SELECT COALESCE(SUM(ppl.amount_cny),0) FROM purchase_payments_link ppl
                 JOIN payments p ON ppl.payment_id=p.id WHERE ppl.purchase_id=%s AND p.is_active=true""", (pid,))
    paid = float(c.fetchone()[0])
    c.execute("SELECT total_amount_cny FROM purchases WHERE id=%s", (pid,))
    tot = float(c.fetchone()[0])
    ps = "paid" if paid >= tot else ("partial" if paid > 0 else "unpaid")
    run("UPDATE purchases SET payment_status=%s WHERE id=%s", ps, pid)

def mk_exp_o(oid, amount, tag):
    c.execute("SELECT COUNT(*) FROM expenses WHERE description=%s", (f"TEST_{tag}",))
    if c.fetchone()[0] > 0: return
    run("""INSERT INTO expenses (id,company_id,category_id,expense_date,currency,amount,
             rate_to_cny,amount_cny,link_type,order_id,is_active,is_reimbursement,description,created_by)
           VALUES (%s,%s,%s,%s,'CNY',%s,1,%s,'order',%s,true,false,%s,%s)""",
        uid(), COMPANY_ID, EXP_DIRECT, TEST_DATE, str(amount), str(amount), oid, f"TEST_{tag}", MANAGER_ID)

def mk_exp_c(cid, amount, tag):
    c.execute("SELECT COUNT(*) FROM expenses WHERE description=%s", (f"TEST_{tag}",))
    if c.fetchone()[0] > 0: return
    run("""INSERT INTO expenses (id,company_id,category_id,expense_date,currency,amount,
             rate_to_cny,amount_cny,link_type,client_id,is_active,is_reimbursement,description,created_by)
           VALUES (%s,%s,%s,%s,'CNY',%s,1,%s,'client',%s,true,false,%s,%s)""",
        uid(), COMPANY_ID, EXP_REPR, TEST_DATE, str(amount), str(amount), cid, f"TEST_{tag}", MANAGER_ID)

def mk_pur_deleted(sid, oid, pnum):
    r = one("SELECT id FROM purchases WHERE purchase_number=%s", pnum)
    if r: return r
    pid = uid()
    run("""INSERT INTO purchases (id,purchase_number,company_id,supplier_id,purchase_date,
             currency,total_amount,rate_to_cny,total_amount_cny,payment_status,order_id,is_deleted,created_by)
           VALUES (%s,%s,%s,%s,%s,'CNY',3000,1,3000,'unpaid',%s,true,%s)""",
        pid, pnum, COMPANY_ID, sid, TEST_DATE, oid, MANAGER_ID)
    return pid

# ═══════════════════════════════════════════════════════════════════════════════
print("Создание/обновление тестовых данных...")
# ═══════════════════════════════════════════════════════════════════════════════

GEN = mk_su("TEST_SUPPLIER_GENERIC")

# S1: fully paid, no expenses → profit=4000, balance=0
c1 = mk_cl("TEST_CLIENT_1_PAID")
o1 = mk_ord(c1, "TEST-S1-001", 10000)
i1 = mk_oi(o1, 10000); mk_pur(GEN, o1, i1, 6000, "TEST-P-S1-001"); mk_pay_o(c1, o1, 10000)

# S2: debt → profit=4000, remaining=6000, balance=-6000
c2 = mk_cl("TEST_CLIENT_2_DEBT")
o2 = mk_ord(c2, "TEST-S2-001", 10000)
i2 = mk_oi(o2, 10000); mk_pur(GEN, o2, i2, 6000, "TEST-P-S2-001"); mk_pay_o(c2, o2, 4000)

# S3: overpayment → balance=+3000
c3 = mk_cl("TEST_CLIENT_3_OVERPAY")
o3 = mk_ord(c3, "TEST-S3-001", 10000)
i3 = mk_oi(o3, 10000); mk_pur(GEN, o3, i3, 6000, "TEST-P-S3-001"); mk_pay_o(c3, o3, 13000)

# S4: direct expense → profit=3000
c4 = mk_cl("TEST_CLIENT_4_DIRECT_EXP")
o4 = mk_ord(c4, "TEST-S4-001", 10000)
i4 = mk_oi(o4, 10000); mk_pur(GEN, o4, i4, 6000, "TEST-P-S4-001"); mk_pay_o(c4, o4, 10000)
mk_exp_o(o4, 1000, "EXP-S4")

# S5: two orders + client expenses → orders profit=8000, client_exp=2000, total=6000
c5 = mk_cl("TEST_CLIENT_5_REPR")
o5a = mk_ord(c5, "TEST-S5-001", 10000); i5a = mk_oi(o5a, 10000)
mk_pur(GEN, o5a, i5a, 6000, "TEST-P-S5-001"); mk_pay_o(c5, o5a, 10000)
o5b = mk_ord(c5, "TEST-S5-002", 10000); i5b = mk_oi(o5b, 10000)
mk_pur(GEN, o5b, i5b, 6000, "TEST-P-S5-002"); mk_pay_o(c5, o5b, 10000)
mk_exp_c(c5, 2000, "REPR-S5")

# S6: 3 orders + direct expense on o2 + client expense
# o1: 15000-8000=7000, o2: 10000-5000-1500=3500, o3: 5000-3000=2000
# orders_profit=12500, client_exp=1000, total=11500, balance=21000-30000=-9000
c6 = mk_cl("TEST_CLIENT_6_MIXED")
o6a = mk_ord(c6, "TEST-S6-001", 15000); i6a = mk_oi(o6a, 15000)
mk_pur(GEN, o6a, i6a, 8000, "TEST-P-S6-001"); mk_pay_o(c6, o6a, 15000)
o6b = mk_ord(c6, "TEST-S6-002", 10000); i6b = mk_oi(o6b, 10000)
mk_pur(GEN, o6b, i6b, 5000, "TEST-P-S6-002"); mk_pay_o(c6, o6b, 6000); mk_exp_o(o6b, 1500, "EXP-S6")
o6c = mk_ord(c6, "TEST-S6-003", 5000); i6c = mk_oi(o6c, 5000)
mk_pur(GEN, o6c, i6c, 3000, "TEST-P-S6-003")
mk_exp_c(c6, 1000, "REPR-S6")

# S7: 1 active + 1 cancelled → only active counted
c7 = mk_cl("TEST_CLIENT_7_CANCELLED")
o7a = mk_ord(c7, "TEST-S7-001", 10000); i7a = mk_oi(o7a, 10000)
mk_pur(GEN, o7a, i7a, 6000, "TEST-P-S7-001"); mk_pay_o(c7, o7a, 10000)
o7b = mk_ord(c7, "TEST-S7-CANCELLED", 5000, status="cancelled")
i7b = mk_oi(o7b, 5000); mk_pur(GEN, o7b, i7b, 3000, "TEST-P-S7-002")

# S8: CNY order, full payment → balance=0
c8 = mk_cl("TEST_CLIENT_8_CURRENCY")
o8 = mk_ord(c8, "TEST-S8-001", 10000)
i8 = mk_oi(o8, 10000); mk_pur(GEN, o8, i8, 6000, "TEST-P-S8-001"); mk_pay_o(c8, o8, 10000)

# S9: two orders both paid → revenue=18000, profit=7000, balance=0
c9 = mk_cl("TEST_CLIENT_9_MULTI")
o9a = mk_ord(c9, "TEST-S9-001", 10000); i9a = mk_oi(o9a, 10000)
mk_pur(GEN, o9a, i9a, 6000, "TEST-P-S9-001"); mk_pay_o(c9, o9a, 10000)
o9b = mk_ord(c9, "TEST-S9-002", 8000); i9b = mk_oi(o9b, 8000)
mk_pur(GEN, o9b, i9b, 5000, "TEST-P-S9-002"); mk_pay_o(c9, o9b, 8000)

# S10: supplier fully paid
s10 = mk_su("TEST_SUPPLIER_10_PAID")
o10 = mk_ord(c1, "TEST-S10-001", 8000); i10 = mk_oi(o10, 8000)
p10 = mk_pur(s10, o10, i10, 5000, "TEST-PURCH-S10-001"); mk_pay_p(s10, p10, 5000)

# S11: supplier debt
s11 = mk_su("TEST_SUPPLIER_11_DEBT")
o11 = mk_ord(c1, "TEST-S11-001", 8000); i11 = mk_oi(o11, 8000)
p11 = mk_pur(s11, o11, i11, 5000, "TEST-PURCH-S11-001"); mk_pay_p(s11, p11, 2000)

# S12: supplier with 3 purchases → total=9000, paid=5500, balance=-3500
s12 = mk_su("TEST_SUPPLIER_12_MULTI")
o12a = mk_ord(c1, "TEST-S12-001", 10000); i12a = mk_oi(o12a, 10000)
p12a = mk_pur(s12, o12a, i12a, 4000, "TEST-PURCH-S12-001"); mk_pay_p(s12, p12a, 4000)
o12b = mk_ord(c1, "TEST-S12-002", 8000); i12b = mk_oi(o12b, 8000)
p12b = mk_pur(s12, o12b, i12b, 3000, "TEST-PURCH-S12-002"); mk_pay_p(s12, p12b, 1500)
o12c = mk_ord(c1, "TEST-S12-003", 6000); i12c = mk_oi(o12c, 6000)
p12c = mk_pur(s12, o12c, i12c, 2000, "TEST-PURCH-S12-003")

# S13: supplier with 1 active + 1 deleted purchase
s13 = mk_su("TEST_SUPPLIER_13_DELETED")
o13a = mk_ord(c1, "TEST-S13-001", 8000); i13a = mk_oi(o13a, 8000)
p13a = mk_pur(s13, o13a, i13a, 5000, "TEST-PURCH-S13-001"); mk_pay_p(s13, p13a, 5000)
o13b = mk_ord(c1, "TEST-S13-002", 8000); i13b = mk_oi(o13b, 8000)
mk_pur_deleted(s13, o13b, "TEST-PURCH-S13-DEL")

# S17: client without orders, only client expense
c17 = mk_cl("TEST_CLIENT_17_NO_ORDERS")
mk_exp_c(c17, 500, "REPR-S17")

# S18: supplier without purchases in period
s18 = mk_su("TEST_SUPPLIER_18_EMPTY")

print("Данные готовы.\n")

# ═══════════════════════════════════════════════════════════════════════════════
print("Запуск проверок...\n")
# ═══════════════════════════════════════════════════════════════════════════════

# ── S1: fully paid, no expenses ───────────────────────────────────────────────
d1 = cdet(c1); s1 = csum(c1)
if d1 and d1.get("orders"):
    r1 = next((x for x in d1["orders"] if x["order_number"]=="TEST-S1-001"), None)
    if r1:
        chk(1,"S1 order profit",4000, r1["profit"],"profit")
        chk(1,"S1 order remaining",0, r1["remaining"],"remaining")
    else: chk_b(1,"S1 order found",False,"TEST-S1-001 missing")
else: chk_b(1,"S1 orders exist",False,"no orders in detail")

# ── S2: debt ──────────────────────────────────────────────────────────────────
d2 = cdet(c2); s2 = csum(c2)
if d2 and d2.get("orders"):
    chk(2,"S2 profit",4000, d2["orders"][0]["profit"],"profit")
    chk(2,"S2 remaining",6000, d2["orders"][0]["remaining"],"remaining")
    chk(2,"S2 balance (debt)",-6000, d2["balance"],"balance")
    if s2: chk(2,"S2 summary balance",-6000, s2["balance"],"sum.balance")
else: chk_b(2,"S2 orders exist",False,"no orders")

# ── S3: overpayment ───────────────────────────────────────────────────────────
d3 = cdet(c3); s3 = csum(c3)
if d3 and d3.get("orders"):
    chk(3,"S3 profit",4000, d3["orders"][0]["profit"],"profit")
    chk(3,"S3 balance (+3000)",3000, d3["balance"],"balance")
    chk_b(3,"S3 balance positive", float(d3["balance"])>0,"overpayment=positive")
    if s3: chk(3,"S3 summary balance",3000, s3["balance"],"sum.balance")
else: chk_b(3,"S3 orders exist",False,"no orders")

# ── S4: direct expense on order ───────────────────────────────────────────────
d4 = cdet(c4)
if d4 and d4.get("orders"):
    chk(4,"S4 profit (10k-6k-1k=3k)",3000, d4["orders"][0]["profit"],"profit")
    chk(4,"S4 direct_exp in order",1000, d4["orders"][0]["direct_expenses"],"direct_exp")
    chk(4,"S4 client_expenses=0",0, d4["client_expenses"],"client_exp=0")
    chk(4,"S4 total_profit",3000, d4["total_profit"],"total_profit")
else: chk_b(4,"S4 orders exist",False,"no orders")

# ── S5: representative expenses ───────────────────────────────────────────────
d5 = cdet(c5)
if d5 and d5.get("orders"):
    chk_b(5,"S5 order count=2", len(d5["orders"])==2, f"got {len(d5['orders'])}")
    for o in d5["orders"]:
        chk(5,f"S5 {o['order_number']} profit=4000",4000, o["profit"],"profit")
        chk(5,f"S5 {o['order_number']} direct_exp=0",0, o["direct_expenses"],"direct_exp=0")
    chk(5,"S5 client_expenses=2000",2000, d5["client_expenses"],"client_exp")
    chk(5,"S5 total_profit (8k-2k)=6000",6000, d5["total_profit"],"total_profit")
else: chk_b(5,"S5 orders exist",False,"no orders")

# ── S6: mixed ─────────────────────────────────────────────────────────────────
d6 = cdet(c6); s6 = csum(c6)
if d6 and d6.get("orders"):
    om = {o["order_number"]:o for o in d6["orders"]}
    chk_b(6,"S6 order count=3", len(d6["orders"])==3, f"got {len(d6['orders'])}")
    if "TEST-S6-001" in om: chk(6,"S6 o1 profit=7000",7000, om["TEST-S6-001"]["profit"],"o1")
    if "TEST-S6-002" in om: chk(6,"S6 o2 profit=3500",3500, om["TEST-S6-002"]["profit"],"o2")
    if "TEST-S6-003" in om: chk(6,"S6 o3 profit=2000",2000, om["TEST-S6-003"]["profit"],"o3")
    chk(6,"S6 client_exp=1000",1000, d6["client_expenses"],"client_exp")
    chk(6,"S6 total_profit=11500",11500, d6["total_profit"],"total_profit")
    chk(6,"S6 balance=-9000",-9000, d6["balance"],"balance")
    if s6: chk(6,"S6 sum.balance",-9000, s6["balance"],"sum.bal")
else: chk_b(6,"S6 orders exist",False,"no orders")

# ── S7: cancelled order excluded ──────────────────────────────────────────────
d7 = cdet(c7)
if d7 is not None:
    chk(7,"S7 count=1",1, len(d7.get("orders",[])),"count")
    if d7.get("orders"):
        chk(7,"S7 active profit=4000",4000, d7["orders"][0]["profit"],"profit")
        nums = [x["order_number"] for x in d7["orders"]]
        chk_b(7,"S7 cancelled excluded","TEST-S7-CANCELLED" not in nums,"cancelled not listed")
else: chk_b(7,"S7 detail returned",False,"None")

# ── S8: CNY payment ───────────────────────────────────────────────────────────
d8 = cdet(c8)
if d8:
    chk(8,"S8 balance=0",0, d8["balance"],"balance")
    chk(8,"S8 profit=4000",4000, d8["total_profit"],"profit")
else: chk_b(8,"S8 detail returned",False,"None")

# ── S9: two orders ────────────────────────────────────────────────────────────
d9 = cdet(c9)
if d9 and d9.get("orders"):
    chk(9,"S9 count=2",2, len(d9["orders"]),"count")
    chk(9,"S9 revenue=18000",18000, d9["total_revenue"],"revenue")
    chk(9,"S9 profit=7000",7000, d9["total_profit"],"profit")
    chk(9,"S9 balance=0",0, d9["balance"],"balance")
else: chk_b(9,"S9 orders exist",False,"no orders")

# ── S10: supplier fully paid ──────────────────────────────────────────────────
d10 = sdet(s10)
if d10 and d10.get("purchases"):
    p = d10["purchases"][0]
    chk(10,"S10 total=5000",5000, p["total_amount_cny"],"total")
    chk(10,"S10 paid=5000",5000, p["paid_cny"],"paid")
    chk(10,"S10 remaining=0",0, p["remaining"],"remaining")
    chk(10,"S10 balance=0",0, d10["balance"],"balance")
    chk_b(10,"S10 status=paid", p["payment_status"]=="paid", f"status={p['payment_status']}")
else: chk_b(10,"S10 purchases exist",False,"no purchases")

# ── S11: supplier debt ────────────────────────────────────────────────────────
d11 = sdet(s11)
if d11 and d11.get("purchases"):
    p = d11["purchases"][0]
    chk(11,"S11 total=5000",5000, p["total_amount_cny"],"total")
    chk(11,"S11 paid=2000",2000, p["paid_cny"],"paid")
    chk(11,"S11 remaining=3000",3000, p["remaining"],"remaining")
    chk(11,"S11 balance=-3000",-3000, d11["balance"],"balance")
else: chk_b(11,"S11 purchases exist",False,"no purchases")

# ── S12: 3 purchases ──────────────────────────────────────────────────────────
d12 = sdet(s12)
if d12 and d12.get("purchases"):
    pm = {p["purchase_number"]:p for p in d12["purchases"]}
    chk(12,"S12 count=3",3, len(d12["purchases"]),"count")
    if "TEST-PURCH-S12-001" in pm: chk(12,"S12 p1 remaining=0",0, pm["TEST-PURCH-S12-001"]["remaining"],"p1")
    if "TEST-PURCH-S12-002" in pm: chk(12,"S12 p2 remaining=1500",1500, pm["TEST-PURCH-S12-002"]["remaining"],"p2")
    if "TEST-PURCH-S12-003" in pm: chk(12,"S12 p3 remaining=2000",2000, pm["TEST-PURCH-S12-003"]["remaining"],"p3")
    for p in d12["purchases"]:
        chk_b(12,f"S12 {p['purchase_number']} has order_number",
              p.get("order_number") is not None, f"={p.get('order_number')}")
    chk(12,"S12 total=9000",9000, d12["total_purchased_cny"],"total")
    chk(12,"S12 paid=5500",5500, d12["total_paid_cny"],"paid")
    chk(12,"S12 balance=-3500",-3500, d12["balance"],"balance")
else: chk_b(12,"S12 purchases exist",False,"no purchases")

# ── S13: deleted purchase excluded ────────────────────────────────────────────
d13 = sdet(s13)
if d13 is not None:
    chk(13,"S13 count=1",1, len(d13.get("purchases",[])),"count")
    if d13.get("purchases"):
        p = d13["purchases"][0]
        chk_b(13,"S13 deleted excluded", p["purchase_number"]!="TEST-PURCH-S13-DEL",
              f"found={p['purchase_number']}")
        chk(13,"S13 total=5000 (active only)",5000, d13["total_purchased_cny"],"total")
else: chk_b(13,"S13 detail returned",False,"None")

# ── S14: summary == detail consistency ────────────────────────────────────────
for cid, tag in [(c2,"S2"),(c3,"S3"),(c5,"S5"),(c6,"S6")]:
    sm = csum(cid); dt = cdet(cid)
    if sm and dt:
        chk(14,f"S14 {tag} balance sum==det", sm["balance"], dt["balance"], f"{tag}.bal")
        chk(14,f"S14 {tag} revenue sum==det", sm["revenue"], dt["total_revenue"], f"{tag}.rev")
        chk(14,f"S14 {tag} profit sum==det",  sm["net_profit"], dt["total_profit"], f"{tag}.profit")
    else: chk_b(14,f"S14 {tag} both exist",False,f"sm={sm is not None} dt={dt is not None}")

# ── S15: P&L no crash ─────────────────────────────────────────────────────────
pnl = api("/api/reports/pnl")
chk_b(15,"S15 PnL returned", pnl is not None,"ok")
if pnl: chk_b(15,"S15 PnL has net_profit","net_profit" in pnl,"key")

# ── S16: Excel export ─────────────────────────────────────────────────────────
rc = sess.get(f"{BASE_URL}/api/reports/by-client/export", params={**PARAMS,"lang":"ru"})
chk_b(16,"S16 client Excel 200", rc.status_code==200, f"status={rc.status_code}")
chk_b(16,"S16 client Excel xlsx","spreadsheetml" in rc.headers.get("content-type",""),
      rc.headers.get("content-type",""))
rs = sess.get(f"{BASE_URL}/api/reports/by-supplier/export", params={**PARAMS,"lang":"ru"})
chk_b(16,"S16 supplier Excel 200", rs.status_code==200, f"status={rs.status_code}")

# ── S17: client without orders ────────────────────────────────────────────────
d17 = cdet(c17)
chk_b(17,"S17 detail returned", d17 is not None,"ok")
if d17:
    chk_b(17,"S17 orders empty", len(d17.get("orders",[]))==0, f"count={len(d17.get('orders',[]))}")
    chk(17,"S17 client_exp=500",500, d17.get("client_expenses",0),"client_exp")
    chk(17,"S17 total_profit=-500",-500, d17.get("total_profit",0),"total_profit")

# ── S18: supplier empty period ────────────────────────────────────────────────
d18 = sdet(s18)
chk_b(18,"S18 detail returned", d18 is not None,"ok")
if d18:
    chk_b(18,"S18 purchases empty", len(d18.get("purchases",[]))==0, f"count={len(d18.get('purchases',[]))}")
    chk(18,"S18 total=0",0, d18.get("total_purchased_cny",-1),"total")

# ── S19: future period no crash ───────────────────────────────────────────────
fp = {"date_from":"2099-01-01","date_to":"2099-12-31"}
chk_b(19,"S19 future pnl ok",    api("/api/reports/pnl",fp) is not None,"ok")
bc_f = api("/api/reports/by-client",fp)
chk_b(19,"S19 future by-client []", isinstance(bc_f,list) and len(bc_f)==0, f"got={bc_f}")
bs_f = api("/api/reports/by-supplier",fp)
chk_b(19,"S19 future by-supplier []", isinstance(bs_f,list) and len(bs_f)==0, f"got={bs_f}")
df = api(f"/api/reports/by-client/{c1}", fp)
chk_b(19,"S19 future client detail ok", df is not None,"ok")
if df: chk_b(19,"S19 future orders empty", len(df.get("orders",[]))==0, f"count={len(df.get('orders',[]))}")

# ── S20: zero denominator in expenses ────────────────────────────────────────
ez = api("/api/reports/expenses", fp)
chk_b(20,"S20 expenses future ok", ez is not None,"ok")
if ez: chk_b(20,"S20 zero total safe", float(ez.get("total",0))==0,"total=0")

# ═══════════════════════════════════════════════════════════════════════════════
# REPORT TABLE
# ═══════════════════════════════════════════════════════════════════════════════
passes = sum(1 for r in results if r["ok"])
fails  = sum(1 for r in results if not r["ok"])

print("\n" + "="*100)
print(f"{'#':<4} {'Сценарий':<42} {'Поле':<24} {'Ожид.':<12} {'Факт.':<12} {'Итог'}")
print("="*100)
for r in results:
    s = "✅" if r["ok"] else "❌"
    print(f"{r['num']:<4} {r['name'][:41]:<42} {r['field'][:23]:<24} "
          f"{str(r['exp'])[:11]:<12} {str(r['got'])[:11]:<12} {s}")
print("="*100)
print(f"\nИТОГО: ✅ {passes}  ❌ {fails}  Всего {passes+fails}")

if fails:
    print("\n⚠️  ПРОВАЛЫ:")
    for r in results:
        if not r["ok"]:
            print(f"  [S{r['num']}] {r['name']} | {r['field']}: ожид={r['exp']}, факт={r['got']}")

print("""
Тестовые данные: все с префиксом TEST_
Удалить: python3 test_reports.py --cleanup
""")
