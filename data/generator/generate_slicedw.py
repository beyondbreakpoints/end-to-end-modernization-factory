"""Builds the SliceDW legacy warehouse load scripts, SSIS package files, and the legacy (wrong) report
numbers, by mirroring the stored procedures in slicedw/02_programmability.sql in Python.

Run last: it reads every source file generated so far.

Output (under <out>/):
  slicedw/03_reference_data.sql, 04_*.sql, 05_run_legacy.sql, ManualAdjustments_March2026.csv, ssis/*.dtsx
  answer_key/slicedw_legacy_*.csv, answer_key/slicedw_vs_true_*.csv
"""
import csv, glob, json, os, sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from common import P, STORES, MENU, business_dates

OUT = sys.argv[1] if len(sys.argv) > 1 else ".."
SQL = os.path.join(OUT, P["slicedw_sql"])
SSIS = os.path.join(OUT, P["ssis"])
KEY = os.path.join(OUT, P["answer_key"])
os.makedirs(SQL, exist_ok=True)
os.makedirs(SSIS, exist_ok=True)
D = Decimal
DATES = business_dates()
P_START, P_END = DATES[0], DATES[-1]


def r2(x):
    return D(x).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def r1(x):
    return D(x).quantize(D("0.1"), rounding=ROUND_HALF_UP)


def q(v):
    """SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, (int, D)):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return "N'" + str(v).replace("'", "''") + "'"


def write_inserts(path, table, cols, rows, batch=500, header=""):
    with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(f"/* {header or table}: {len(rows)} rows */\nSET NOCOUNT ON;\n")
        for i in range(0, len(rows), batch):
            f.write(f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n")
            f.write(",\n".join("(" + ", ".join(q(v) for v in r) + ")" for r in rows[i:i + batch]))
            f.write(";\nGO\n")


def read_csv(path, delimiter=","):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


# ================================================================== read the source files
mh, md = [], []
for f in sorted(glob.glob(os.path.join(OUT, P["micros"], "check_header_*.txt"))):
    mh += read_csv(f, "|")
for f in sorted(glob.glob(os.path.join(OUT, P["micros"], "check_detail_*.txt"))):
    md += read_csv(f, "|")
ac, ai = [], []
for f in sorted(glob.glob(os.path.join(OUT, P["aloha"], "*", "*", "CHECKS.csv"))):
    ac += read_csv(f)
for f in sorted(glob.glob(os.path.join(OUT, P["aloha"], "*", "*", "ITEMS.csv"))):
    ai += read_csv(f)
orders = []
for f in sorted(glob.glob(os.path.join(OUT, P["online"], "orders_*.json"))):
    with open(f, encoding="utf-8") as fh:
        orders += json.load(fh)
customers = read_csv(os.path.join(OUT, P["online"], "customers.csv"))
cdir = os.path.join(OUT, P["commissary"])
with open(os.path.join(cdir, "ITEMMAST.TXT")) as f:
    itemmast = [l.rstrip("\r\n") for l in f if l.strip()]
shipments = []
for fpath in sorted(glob.glob(os.path.join(cdir, "SHP*.TXT"))):
    with open(fpath) as f:
        shipments += [(os.path.basename(fpath), n, l.rstrip("\r\n")) for n, l in enumerate(f, 1) if l.strip()]
counts = []
for fpath in sorted(glob.glob(os.path.join(cdir, "CNT*.TXT"))):
    with open(fpath) as f:
        counts += [(os.path.basename(fpath), n, l.rstrip("\r\n")) for n, l in enumerate(f, 1) if l.strip()]
stores = read_csv(os.path.join(OUT, P["master"], "stores.csv"))
menu = read_csv(os.path.join(OUT, P["master"], "menu.csv"))
recipes = read_csv(os.path.join(OUT, P["master"], "recipes.csv"))
calendar = read_csv(os.path.join(OUT, P["master"], "calendar.csv"))


def us_ts(s):          # 03/14/2026 01:54 -> datetime
    return datetime.strptime(s, "%m/%d/%Y %H:%M")


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ================================================================== legacy configuration
# Aloha map keyed in by hand after the acquisition: four items never mapped, one mapped to the wrong size
ALOHA_MAP = {m[7]: m[0] for m in MENU if m[7] not in ("WING10", "CINN", "CAESAR", "POPCAN")}
ALOHA_MAP["MDVEG"] = "PZ-VEG-L"
ROYALTY_TERMS = [("ROYALTY_RATE", "0.0500", "Franchise agreement s.7.1"),
                 ("AD_FUND_RATE", "0.0300", "Franchise agreement s.7.3"),
                 ("NEW_STORE_HOLIDAY_MONTHS", "6.0000", "Franchise agreement s.7.5: no royalty or ad fund for the first 6 months")]
ORG = [(1, None, "Polar Slice Pizza", "COMPANY", None),
       (10, 1, "Greater Toronto", "REGION", None), (20, 1, "Eastern and Central Ontario", "REGION", None),
       (11, 10, "Toronto", "DISTRICT", None), (12, 10, "West GTA and Hamilton", "DISTRICT", None),
       (21, 20, "Ottawa and Kingston", "DISTRICT", None), (22, 20, "Barrie", "DISTRICT", None)]
DISTRICT = {1042: 11, 1043: 11, 3015: 11, 1055: 12, 1061: 12, 1078: 12, 1090: 12, 2207: 21, 2214: 21, 2231: 22}
for s in STORES:
    ORG.append((s[0], DISTRICT[s[0]], f"{s[0]} {s[1]}", "STORE", s[0]))
ADJUSTMENTS = [  # store, date, type, amount, note, keyed_by, keyed_at
    (1042, "2026-03-11", "MARKETING_CREDIT", D("-150.00"), "Local marketing co-op credit, approval M-2231", "jlam", "2026-03-11 16:02:00"),
    (1055, "2026-03-10", "MARKETING_CREDIT", D("-120.00"), "Square One reopening flyer credit", "jlam", "2026-03-10 10:15:00"),
    (2207, "2026-03-12", "EQUIP_RECOVERY", D("85.00"), "Oven repair recharge, ticket 4471", "mpatel", "2026-03-12 14:40:00"),
    (1055, "2026-03-10", "MARKETING_CREDIT", D("-120.00"), "Square One reopening flyer credit", "mpatel", "2026-03-11 09:05:00"),
    (1090, "2026-03-13", "LATE_FEE", D("25.00"), "Late payment fee, February invoice", "jlam", "2026-03-13 11:20:00"),
]
DUPLICATE_ADJ_INDEX = 3   # keyed twice by two different people

# ================================================================== 03 reference data
with open(os.path.join(SQL, "03_reference_data.sql"), "w", encoding="utf-8-sig", newline="\n") as f:
    f.write("/* SliceDW reference data. Run after 02_programmability.sql */\nSET NOCOUNT ON;\n")

    def block(table, cols, rows):
        f.write(f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n")
        f.write(",\n".join("(" + ", ".join(q(v) for v in r) + ")" for r in rows) + ";\n")

    block("cfg.Store", ["store_id", "store_name", "city", "province", "ownership", "franchisee_id", "franchisee_name",
                        "pos_system", "open_date"],
          [[int(s["store_id"]), s["store_name"], s["city"], s["province"], s["ownership"], s["franchisee_id"] or None,
            s["franchisee_name"] or None, s["pos_system"], s["open_date"]] for s in stores])
    block("cfg.MenuItem", ["sku", "item_name", "category", "size", "price_excl_tax", "micros_item_no"],
          [[m["sku"], m["item_name"], m["category"], m["size"] or None, D(m["price_excl_tax"]), int(m["micros_item_no"])]
           for m in menu])
    block("cfg.AlohaItemMap", ["aloha_item_code", "sku", "mapped_by", "mapped_on"],
          [[code, sku, "kdesai", "2022-07-18T10:30:00"] for code, sku in sorted(ALOHA_MAP.items())])
    block("cfg.Recipe", ["sku", "ingredient_item_code", "qty_per_unit", "base_uom"],
          [[r["sku"], r["ingredient_item_code"], D(r["qty_per_unit"]), r["base_uom"]] for r in recipes])
    block("cfg.RoyaltyTerm", ["term_code", "term_value", "note"], [[a, D(b), c] for a, b, c in ROYALTY_TERMS])
    f.write("INSERT INTO cfg.OrgUnit (unit_id, parent_unit_id, unit_name, unit_type, store_id) VALUES\n")
    f.write(",\n".join("(" + ", ".join(q(v) for v in r) + ")" for r in ORG) + ";\n")
    block("dw.DimDate", ["date_key", "calendar_date", "day_name", "is_2for1"],
          [[int(c["business_date"].replace("-", "")), c["business_date"], c["day_name"],
            1 if c["is_2for1_tuesday"] == "Y" else 0] for c in calendar])
    block("adj.ManualAdjustment", ["store_id", "business_date", "adj_type", "amount", "note", "keyed_by", "keyed_at"],
          [[a[0], a[1], a[2], a[3], a[4], a[5], a[6].replace(" ", "T")] for a in ADJUSTMENTS])
    f.write("GO\n")

with open(os.path.join(OUT, P["slicedw"], "ManualAdjustments_March2026.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Store", "Date", "Type", "Amount", "Note", "Keyed by", "Keyed at"])
    for a in ADJUSTMENTS:
        w.writerow([a[0], a[1], a[2], f"{a[3]:.2f}", a[4], a[5], a[6]])

# ================================================================== 04 staging data (what SSIS landed)
write_inserts(os.path.join(SQL, "04a_stg_micros_check_header.sql"), "stg.micros_check_header",
              ["store", "business_date", "check_no", "open_time", "close_time", "order_type", "guest_count", "subtotal",
               "discount", "tax", "tip", "total", "tender", "void_flag", "online_ref", "employee_id"],
              [[int(h["store"]), h["business_date"], int(h["check_no"]), h["open_time"], h["close_time"], h["order_type"],
                int(h["guest_count"]), D(h["subtotal"]), D(h["discount"]), D(h["tax"]), D(h["tip"]), D(h["total"]),
                h["tender"], h["void_flag"], h["online_ref"] or None, h["employee_id"]] for h in mh])
write_inserts(os.path.join(SQL, "04b_stg_micros_check_detail.sql"), "stg.micros_check_detail",
              ["store", "business_date", "check_no", "line_no", "item_no", "item_name", "qty", "unit_price", "line_amount", "line_type"],
              [[int(r["store"]), r["business_date"], int(r["check_no"]), int(r["line_no"]), int(r["item_no"]), r["item_name"],
                int(r["qty"]), D(r["unit_price"]), D(r["line_amount"]), r["line_type"]] for r in md])
write_inserts(os.path.join(SQL, "04c_stg_aloha_checks.sql"), "stg.aloha_checks",
              ["store", "dob", "checkid", "tablenum", "ordermode", "opentime", "closetime", "gross", "comp", "nettotal",
               "taxincl", "tip", "total", "paytype", "employee"],
              [[int(c["STORE"]), c["DOB"], int(c["CHECKID"]), c["TABLENUM"] or None, c["ORDERMODE"], iso(us_ts(c["OPENTIME"])),
                iso(us_ts(c["CLOSETIME"])), D(c["GROSS"]), D(c["COMP"]), D(c["NETTOTAL"]), D(c["TAXINCL"]), D(c["TIP"]),
                D(c["TOTAL"]), c["PAYTYPE"], c["EMPLOYEE"]] for c in ac])
write_inserts(os.path.join(SQL, "04d_stg_aloha_items.sql"), "stg.aloha_items",
              ["store", "dob", "checkid", "entryid", "itemcode", "itemname", "qty", "price", "amount", "type", "ordertime"],
              [[int(i["STORE"]), i["DOB"], int(i["CHECKID"]), int(i["ENTRYID"]), i["ITEMCODE"], i["ITEMNAME"], int(i["QTY"]),
                D(i["PRICE"]), D(i["AMOUNT"]), i["TYPE"], iso(us_ts(i["ORDERTIME"]))] for i in ai])
dec = lambda x: D(str(x)).quantize(D("0.01"))
write_inserts(os.path.join(SQL, "04e_stg_online_order.sql"), "stg.online_order",
              ["order_id", "placed_at", "store_id", "channel", "fulfilment", "status", "promo_code", "customer_id",
               "customer_name", "customer_email", "customer_phone", "subtotal", "discount", "tax", "tip", "total", "pos_check_no"],
              [[o["order_id"], o["placed_at"], o["store_id"], o["channel"], o["fulfilment"], o["status"], o["promo_code"],
                o["customer"]["id"], o["customer"]["name"], o["customer"]["email"], o["customer"]["phone"],
                dec(o["subtotal"]), dec(o["discount"]), dec(o["tax"]), dec(o["tip"]), dec(o["total"]), o["pos_check_no"]]
               for o in orders])
write_inserts(os.path.join(SQL, "04f_stg_online_order_item.sql"), "stg.online_order_item",
              ["order_id", "line_no", "sku", "item_name", "qty", "unit_price"],
              [[o["order_id"], n, it["sku"], it["name"], it["qty"], dec(it["unit_price"])]
               for o in orders for n, it in enumerate(o["items"], 1)])
write_inserts(os.path.join(SQL, "04g_stg_online_customer.sql"), "stg.online_customer",
              ["customer_id", "full_name", "email", "phone", "created_at", "home_store_id", "loyalty_points", "marketing_opt_in"],
              [[int(c["customer_id"]), c["full_name"], c["email"], c["phone"], c["created_at"].replace(" ", "T"),
                int(c["home_store_id"]), int(c["loyalty_points"]), int(c["marketing_opt_in"])] for c in customers])
with open(os.path.join(SQL, "04h_stg_commissary.sql"), "w", newline="\n") as f:
    f.write("/* AS/400 commissary raw lines */\nSET NOCOUNT ON;\n")
    f.write("INSERT INTO stg.as400_itemmast_raw (raw_line) VALUES\n" + ",\n".join(f"('{l}')" for l in itemmast) + ";\n")
    f.write("INSERT INTO stg.as400_shipment_raw (file_name, line_no, raw_line) VALUES\n" +
            ",\n".join(f"('{a}', {n}, '{l}')" for a, n, l in shipments) + ";\n")
    f.write("INSERT INTO stg.as400_count_raw (file_name, line_no, raw_line) VALUES\n" +
            ",\n".join(f"('{a}', {n}, '{l}')" for a, n, l in counts) + ";\nGO\n")

with open(os.path.join(SQL, "05_run_legacy.sql"), "w", newline="\n") as f:
    f.write(f"""/* Run the legacy nightly and period processing for the dev slice, then look at the results */
EXEC dw.usp_RunPeriod @PeriodStart = '{P_START}', @PeriodEnd = '{P_END}';
GO
SELECT * FROM rpt.vw_DailySales ORDER BY business_date, store_id;
SELECT * FROM rpt.RoyaltyInvoice ORDER BY franchisee_id, store_id;
SELECT * FROM rpt.FoodCostVariance WHERE item_code = 'MOZ00410' ORDER BY store_id;
SELECT * FROM rpt.PromoCost ORDER BY business_date, store_id, promo_name;
SELECT * FROM cfg.EtlRunLog ORDER BY run_id;
""")

# ================================================================== mirror of the stored procedures
micros_sku = {m["micros_item_no"]: m["sku"] for m in menu}
store_info = {int(s["store_id"]): s for s in stores}
fact_check = []        # dicts
fact_line = []
fact_online = []
daily = {}
promo = defaultdict(D)
for d in DATES:
    ds = d.isoformat()
    # usp_LoadFactCheckMicros
    fc_m = [h for h in mh if h["business_date"] == ds and h["void_flag"] == "N"]
    for h in fc_m:
        fact_check.append({"store": int(h["store"]), "date": ds, "src": "MICROS", "check_id": h["check_no"],
                           "gross": D(h["subtotal"]), "discount": D(h["discount"]), "tax": D(h["tax"]),
                           "net": D(h["subtotal"]) - D(h["discount"])})
    for r in md:
        if r["business_date"] == ds and r["line_type"] in ("ITEM", "GIFT"):
            fact_line.append({"store": int(r["store"]), "date": ds, "sku": micros_sku.get(r["item_no"]), "qty": int(r["qty"])})
    # usp_LoadFactCheckAloha
    for c in ac:
        if us_ts(c["CLOSETIME"]).date() == d:
            fact_check.append({"store": int(c["STORE"]), "date": ds, "src": "ALOHA", "check_id": f'{c["DOB"]}-{c["CHECKID"]}',
                               "gross": D(c["GROSS"]), "discount": D(c["COMP"]), "tax": D(c["TAXINCL"]),
                               "net": D(c["NETTOTAL"])})
    closed_today = {(c["STORE"], c["DOB"], c["CHECKID"]) for c in ac if us_ts(c["CLOSETIME"]).date() == d}
    for i in ai:
        if i["TYPE"] == "ITEM" and (i["STORE"], i["DOB"], i["CHECKID"]) in closed_today:
            fact_line.append({"store": int(i["STORE"]), "date": ds, "sku": ALOHA_MAP.get(i["ITEMCODE"]), "qty": int(i["QTY"])})
    # usp_LoadFactOnline + usp_DedupOnline
    micros_checks = {(f["store"], f["check_id"]) for f in fact_check if f["date"] == ds and f["src"] == "MICROS"}
    for o in orders:
        if o["placed_at"][:10] == ds and o["status"] != "refunded":
            dup = o["pos_check_no"] is not None and (o["store_id"], str(o["pos_check_no"])) in micros_checks
            fact_online.append({"store": o["store_id"], "date": ds, "order_id": o["order_id"], "status": o["status"],
                                "net": dec(o["subtotal"]) - dec(o["discount"]), "dup": dup,
                                "aloha": o["pos_check_no"] is None and o["status"] == "completed"})
    # usp_BuildNetSales
    todays = [f for f in fact_check if f["date"] == ds]
    online_today = [o for o in fact_online if o["date"] == ds and not o["dup"]]
    for st in sorted({f["store"] for f in todays} | {o["store"] for o in online_today}):
        t = [f for f in todays if f["store"] == st]
        tills = sum((f["net"] for f in t), D("0"))
        onl = sum((o["net"] for o in online_today if o["store"] == st), D("0"))
        voids = -sum((D(h["subtotal"]) for h in mh if h["business_date"] == ds and h["void_flag"] == "V" and int(h["store"]) == st), D("0"))
        daily[(st, ds)] = {"gross": sum((f["gross"] for f in t), D("0")), "disc": sum((f["discount"] for f in t), D("0")),
                           "voids": voids, "tills": tills, "online": onl, "net": tills + onl,
                           "tax": sum((f["tax"] for f in t), D("0")), "checks": len(t)}
    # usp_BuildPromoCost
    for r in md:
        if r["business_date"] == ds and r["line_type"] == "DISC":
            name = {"9001": "2FOR1TUE", "9002": "WELCOME10"}.get(r["item_no"], "STAFF50")
            promo[(int(r["store"]), ds, name)] += -D(r["line_amount"])
    for i in ai:
        if i["TYPE"] == "COMP" and us_ts(i["ORDERTIME"]).date() == d:
            name = "2FOR1TUE" if i["ITEMCODE"] == "2F1TUE" else "STAFF50"
            promo[(int(i["STORE"]), ds, name)] += -D(i["AMOUNT"])

# usp_CalcRoyalty
def months_back(d, n):
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    from calendar import monthrange
    return date(y, m, min(d.day, monthrange(y, m)[1]))


legacy_royalty = []
for st, s in sorted(store_info.items()):
    net = sum((v["net"] for (k, ds), v in daily.items() if k == st), D("0"))
    if s["ownership"] != "FRANCHISE" or date.fromisoformat(s["open_date"]) > months_back(P_END, 3):
        continue
    adj = sum((a[3] for a in ADJUSTMENTS if a[0] == st and P_START.isoformat() <= a[1] <= P_END.isoformat()), D("0"))
    roy, ad = r2(net * D("0.05")), r2(net * D("0.03"))
    legacy_royalty.append([s["franchisee_id"], s["franchisee_name"], st, net, roy, ad, adj, roy + ad + adj])

# usp_LoadCommissary + usp_CalcFoodCost
item = {l[0:8]: {"desc": l[8:28].rstrip(), "pack_qty": D(l[32:39]) / 1000, "pack_cost": D(l[39:46]) / 100} for l in itemmast}
received = defaultdict(D)
for _, _, l in shipments:
    ship_date = date(1900 + int(l[5]) * 100 + int(l[6:8]), int(l[8:10]), int(l[10:12]))
    if P_START <= ship_date <= P_END:
        received[(int(l[0:5]), l[12:20])] += D(l[40:47]) / 100 * item[l[12:20]]["pack_qty"]
cnt = {}
for _, _, l in counts:
    cnt[(int(l[0:5]), l[13:21], l[12])] = D(l[21:29]) / 1000
recipe = defaultdict(list)
for r in recipes:
    recipe[r["sku"]].append((r["ingredient_item_code"], D(r["qty_per_unit"])))
theo = defaultdict(D)
for l in fact_line:
    if l["sku"]:
        for code, per in recipe[l["sku"]]:
            theo[(l["store"], code)] += per * l["qty"]
legacy_food = []
for (st, code, kind), opening in sorted(cnt.items()):
    if kind != "O":
        continue
    closing = cnt[(st, code, "C")]
    rec = received[(st, code)]
    actual = opening + rec - closing
    t = theo[(st, code)]
    var = actual - t
    pct = r1(var / t * 100) if t else None
    cost = r2(var * item[code]["pack_cost"] / item[code]["pack_qty"])
    legacy_food.append([st, code, item[code]["desc"], opening, rec, closing, actual, t, var, pct, cost])

# ================================================================== write the legacy numbers
def fmt(v, places=2):
    if v is None:
        return ""
    if isinstance(v, D):
        return f"{v:.{places}f}"
    return str(v)


with open(os.path.join(KEY, "slicedw_legacy_daily_sales.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store_id", "business_date", "gross_sales", "discounts", "voids", "net_sales_tills", "online_only_sales",
                "net_sales", "tax", "check_count"])
    for (st, ds), v in sorted(daily.items(), key=lambda x: (x[0][1], x[0][0])):
        w.writerow([st, ds] + [fmt(v[k]) for k in ("gross", "disc", "voids", "tills", "online", "net", "tax")] + [v["checks"]])
with open(os.path.join(KEY, "slicedw_legacy_royalty.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["franchisee_id", "franchisee_name", "store_id", "period_start", "period_end", "net_sales", "royalty",
                "ad_fund", "adjustments", "amount_due"])
    for r in legacy_royalty:
        w.writerow([r[0], r[1], r[2], P_START, P_END] + [fmt(v) for v in r[3:]])
with open(os.path.join(KEY, "slicedw_legacy_food_cost.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store_id", "item_code", "item_desc", "opening_qty", "received_qty", "closing_qty", "actual_usage",
                "theoretical_usage", "variance", "variance_pct", "variance_cost"])
    for r in legacy_food:
        w.writerow(r[:3] + [fmt(v, 3) for v in r[3:9]] + [fmt(r[9], 1), fmt(r[10])])
with open(os.path.join(KEY, "slicedw_legacy_promo_cost.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store_id", "business_date", "promo_name", "discount_amount"])
    for (st, ds, name), v in sorted(promo.items(), key=lambda x: (x[0][1], x[0][0], x[0][2])):
        w.writerow([st, ds, name, fmt(v)])

# ================================================================== legacy vs true, with the reasons
true_net = {}
for r in read_csv(os.path.join(KEY, "micros_true_net_sales.csv")):
    true_net[(int(r["store"]), r["business_date"])] = D(r["net_sales"])
for r in read_csv(os.path.join(KEY, "aloha_true_net_sales.csv")):
    true_net[(int(r["store"]), r["business_date"])] = D(r["net_sales"])
period = {d.isoformat() for d in DATES}
seen, dup_keys = set(), set()
for h in mh:
    k = (h["store"], h["business_date"], h["check_no"], h["void_flag"])
    if k in seen:
        dup_keys.add(k)
    seen.add(k)
voided = {(h["store"], h["check_no"]) for h in mh if h["void_flag"] == "V"}

causes = defaultdict(lambda: defaultdict(D))      # store -> cause -> amount (effect on legacy net sales)
seen = set()
for h in mh:
    if h["business_date"] not in period or h["void_flag"] != "N":
        continue
    st, net = int(h["store"]), D(h["subtotal"]) - D(h["discount"])
    k = (h["store"], h["business_date"], h["check_no"], h["void_flag"])
    if k in seen:
        causes[st]["duplicate_polling"] += net
        continue
    seen.add(k)
    if h["order_type"] == "GIFT":
        causes[st]["gift_card_loads"] += net
    elif (h["store"], h["check_no"]) in voided:
        causes[st]["voids_not_subtracted"] += net
for c in ac:
    st = int(c["STORE"])
    net_incl, tax = D(c["NETTOTAL"]), D(c["TAXINCL"])
    in_by_close = us_ts(c["CLOSETIME"]).date().isoformat() in period
    in_by_dob = f'{c["DOB"][:4]}-{c["DOB"][4:6]}-{c["DOB"][6:]}' in period
    if in_by_close:
        causes[st]["aloha_tax_included"] += tax
    causes[st]["aloha_business_day"] += (net_incl - tax) * (int(in_by_close) - int(in_by_dob))
for o in fact_online:
    if o["dup"]:
        continue
    key = "cancelled_orders" if o["status"] == "cancelled" else "online_counted_twice"
    causes[o["store"]][key] += o["net"]

CAUSE_COLS = ["gift_card_loads", "voids_not_subtracted", "duplicate_polling", "aloha_tax_included",
              "aloha_business_day", "online_counted_twice", "cancelled_orders"]
with open(os.path.join(KEY, "slicedw_vs_true_net_sales.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store_id", "legacy_net_sales", "true_net_sales", "difference"] + CAUSE_COLS + ["unexplained"])
    for st in sorted(store_info):
        leg = sum((v["net"] for (k, ds), v in daily.items() if k == st), D("0"))
        tru = sum((v for (k, ds), v in true_net.items() if k == st and ds in period), D("0"))
        parts = [causes[st][c] for c in CAUSE_COLS]
        w.writerow([st, fmt(leg), fmt(tru), fmt(leg - tru)] + [fmt(p) for p in parts] + [fmt(leg - tru - sum(parts))])

legit_adj = [a for n, a in enumerate(ADJUSTMENTS) if n != DUPLICATE_ADJ_INDEX]
with open(os.path.join(KEY, "slicedw_vs_true_royalty.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["franchisee_id", "franchisee_name", "store_id", "legacy_amount_due", "true_amount_due", "difference",
                "note"])
    legacy_by_store = {r[2]: r for r in legacy_royalty}
    for st, s in sorted(store_info.items()):
        if s["ownership"] != "FRANCHISE":
            continue
        opened = date.fromisoformat(s["open_date"])
        on_holiday = opened > months_back(P_END, 6)
        tru_net = sum((v for (k, ds), v in true_net.items() if k == st and ds in period), D("0"))
        adj = sum((a[3] for a in legit_adj if a[0] == st), D("0"))
        tru_due = adj if on_holiday else r2(tru_net * D("0.05")) + r2(tru_net * D("0.03")) + adj
        leg_due = legacy_by_store[st][7] if st in legacy_by_store else D("0")
        notes = []
        if on_holiday and st in legacy_by_store:
            notes.append("Within its 6-month royalty holiday, but the procedure only allows 3 months")
        if st in legacy_by_store and legacy_by_store[st][3] != tru_net:
            notes.append("Legacy net sales are wrong (see slicedw_vs_true_net_sales.csv)")
        if any(a[0] == st for n, a in enumerate(ADJUSTMENTS) if n == DUPLICATE_ADJ_INDEX):
            notes.append("A marketing credit was keyed in twice")
        w.writerow([s["franchisee_id"], s["franchisee_name"], st, fmt(leg_due), fmt(tru_due), fmt(leg_due - tru_due),
                    "; ".join(notes)])

# ================================================================== SSIS packages (simplified .dtsx)
DTS = 'xmlns:DTS="www.microsoft.com/SqlServer/Dts"'
OLEDB = ('<DTS:ConnectionManager DTS:ObjectName="OLEDB_SliceDW" DTS:CreationName="OLEDB" DTS:DTSID="{6F1D2A10-0B6B-4C2E-9D11-5A1D0C0A0001}">'
         '<DTS:ObjectData><DTS:ConnectionManager DTS:ConnectionString="Data Source=PSSQL01;Initial Catalog=SliceDW;'
         'Provider=SQLNCLI11.1;Integrated Security=SSPI;" /></DTS:ObjectData></DTS:ConnectionManager>')


def flat_conn(name, path, fmt_, delim=None, extra=""):
    d = f' DTS:ColumnDelimiter="{delim}"' if delim else ""
    return (f'<DTS:ConnectionManager DTS:ObjectName="{name}" DTS:CreationName="FLATFILE">'
            f'<DTS:ObjectData><DTS:ConnectionManager DTS:ConnectionString="{path}" DTS:Format="{fmt_}"{d} '
            f'DTS:ColumnNamesInFirstDataRow="{"True" if fmt_ == "Delimited" else "False"}"{extra} /></DTS:ObjectData>'
            f'</DTS:ConnectionManager>')


def data_flow(name, source_conn, source_class, target_table, transforms=()):
    comps = [f'<component name="SRC {source_conn}" componentClassID="{source_class}">'
             f'<connections><connection connectionManagerRefId="Package.ConnectionManagers[{source_conn}]" /></connections></component>']
    for t_name, t_class, expr in transforms:
        comps.append(f'<component name="{t_name}" componentClassID="{t_class}"><properties>'
                     f'<property name="Expression">{expr}</property></properties></component>')
    comps.append(f'<component name="DST {target_table}" componentClassID="Microsoft.OLEDBDestination"><properties>'
                 f'<property name="OpenRowset">{target_table}</property><property name="AccessMode">3</property>'
                 f'</properties><connections><connection connectionManagerRefId="Package.ConnectionManagers[OLEDB_SliceDW]" />'
                 f'</connections></component>')
    return (f'  <DTS:Executable DTS:refId="Package\\{name}" DTS:ExecutableType="Microsoft.Pipeline" DTS:ObjectName="{name}">\n'
            f'   <DTS:ObjectData><pipeline version="1"><components>\n    ' + "\n    ".join(comps) +
            '\n   </components></pipeline></DTS:ObjectData>\n  </DTS:Executable>')


def sql_task(name, statement):
    return (f'  <DTS:Executable DTS:refId="Package\\{name}" DTS:ExecutableType="Microsoft.ExecuteSQLTask" DTS:ObjectName="{name}">\n'
            f'   <DTS:ObjectData><SQLTask:SqlTaskData xmlns:SQLTask="www.microsoft.com/sqlserver/dts/tasks/sqltask" '
            f'SQLTask:Connection="OLEDB_SliceDW" SQLTask:SqlStatementSource="{statement}" /></DTS:ObjectData>\n  </DTS:Executable>')


def package(name, created, conns, executables, constraints=()):
    pc = "".join(f'\n  <DTS:PrecedenceConstraint DTS:From="Package\\{a}" DTS:To="Package\\{b}" DTS:Value="Success" />'
                 for a, b in constraints)
    xml = (f'<?xml version="1.0"?>\n<DTS:Executable {DTS} DTS:refId="Package" DTS:ExecutableType="Microsoft.Package" '
           f'DTS:ObjectName="{name}" DTS:CreationDate="{created}" DTS:CreatorName="POLARSLICE\\etl_svc" '
           f'DTS:CreatorComputerName="PSETL01" DTS:VersionBuild="{len(name) * 3}">\n'
           f' <DTS:ConnectionManagers>\n  ' + "\n  ".join(conns) + '\n </DTS:ConnectionManagers>\n'
           f' <DTS:Executables>\n' + "\n".join(executables) + '\n </DTS:Executables>\n'
           f' <DTS:PrecedenceConstraints>{pc}\n </DTS:PrecedenceConstraints>\n</DTS:Executable>\n')
    with open(os.path.join(SSIS, f"{name}.dtsx"), "w", newline="\n") as f:
        f.write(xml)


package("LoadTills", "03/14/2019 09:12:44",
        [OLEDB, flat_conn("FF_MicrosHeader", r"\\psfs01\polling\micros\check_header_*.txt", "Delimited", "|"),
         flat_conn("FF_MicrosDetail", r"\\psfs01\polling\micros\check_detail_*.txt", "Delimited", "|"),
         flat_conn("FF_AlohaChecks", r"\\psfs01\polling\aloha\*\*\CHECKS.csv", "Delimited", ","),
         flat_conn("FF_AlohaItems", r"\\psfs01\polling\aloha\*\*\ITEMS.csv", "Delimited", ",")],
        [data_flow("DFT MICROS headers", "FF_MicrosHeader", "Microsoft.FlatFileSource", "[stg].[micros_check_header]",
                   [("DER load_ts", "Microsoft.DerivedColumn", "GETDATE()")]),
         data_flow("DFT MICROS details", "FF_MicrosDetail", "Microsoft.FlatFileSource", "[stg].[micros_check_detail]",
                   [("DER load_ts", "Microsoft.DerivedColumn", "GETDATE()")]),
         data_flow("DFT Aloha checks", "FF_AlohaChecks", "Microsoft.FlatFileSource", "[stg].[aloha_checks]",
                   [("DER parse US timestamps", "Microsoft.DerivedColumn", "(DT_DBTIMESTAMP)OPENTIME; (DT_DBTIMESTAMP)CLOSETIME")]),
         data_flow("DFT Aloha items", "FF_AlohaItems", "Microsoft.FlatFileSource", "[stg].[aloha_items]",
                   [("DER parse US timestamps", "Microsoft.DerivedColumn", "(DT_DBTIMESTAMP)ORDERTIME")])],
        [("DFT MICROS headers", "DFT MICROS details"), ("DFT Aloha checks", "DFT Aloha items")])

package("LoadOnline", "11/02/2022 15:40:03",
        [OLEDB, flat_conn("FF_OnlineOrders", r"\\psfs01\exports\online\orders_*.json", "RaggedRight"),
         flat_conn("FF_Customers", r"\\psfs01\exports\online\customers.csv", "Delimited", ",")],
        [data_flow("DFT Online orders", "FF_OnlineOrders", "Microsoft.ScriptComponent", "[stg].[online_order]",
                   [("SCR split order items", "Microsoft.ScriptComponent", "JSON parser (C#): one output per order, one per item")]),
         data_flow("DFT Online order items", "FF_OnlineOrders", "Microsoft.ScriptComponent", "[stg].[online_order_item]"),
         data_flow("DFT Customers", "FF_Customers", "Microsoft.FlatFileSource", "[stg].[online_customer]")],
        [("DFT Online orders", "DFT Online order items")])

package("LoadCommissary", "06/22/2017 08:05:51",
        [OLEDB, flat_conn("FF_ItemMast", r"\\as400ifs\exports\ITEMMAST.TXT", "FixedWidth"),
         flat_conn("FF_Shipments", r"\\as400ifs\exports\SHP*.TXT", "FixedWidth"),
         flat_conn("FF_Counts", r"\\as400ifs\exports\CNT*.TXT", "FixedWidth")],
        [data_flow("DFT Item master", "FF_ItemMast", "Microsoft.FlatFileSource", "[stg].[as400_itemmast_raw]"),
         data_flow("DFT Shipments", "FF_Shipments", "Microsoft.FlatFileSource", "[stg].[as400_shipment_raw]",
                   [("DER file name and line", "Microsoft.DerivedColumn", "@[User::FileName]; @[User::LineNo]")]),
         data_flow("DFT Counts", "FF_Counts", "Microsoft.FlatFileSource", "[stg].[as400_count_raw]",
                   [("DER file name and line", "Microsoft.DerivedColumn", "@[User::FileName]; @[User::LineNo]")])])

package("LoadAdjustments", "01/09/2023 11:27:16",
        [OLEDB, '<DTS:ConnectionManager DTS:ObjectName="XL_Adjustments" DTS:CreationName="EXCEL"><DTS:ObjectData>'
                '<DTS:ConnectionManager DTS:ConnectionString="Provider=Microsoft.ACE.OLEDB.12.0;Data Source=\\\\psfs01\\finance\\'
                'royalty\\ManualAdjustments_*.xlsx;Extended Properties=&quot;Excel 12.0 XML;HDR=YES&quot;;" /></DTS:ObjectData>'
                '</DTS:ConnectionManager>'],
        [data_flow("DFT Manual adjustments", "XL_Adjustments", "Microsoft.ExcelSource", "[adj].[ManualAdjustment]")])


def exec_pkg(name):
    return (f'  <DTS:Executable DTS:refId="Package\\EPT {name}" DTS:ExecutableType="Microsoft.ExecutePackageTask" '
            f'DTS:ObjectName="EPT {name}"><DTS:ObjectData><ExecutePackageTask><PackageName>{name}.dtsx</PackageName>'
            f'</ExecutePackageTask></DTS:ObjectData></DTS:Executable>')


package("Nightly_Master", "03/14/2019 10:01:12", [OLEDB],
        [exec_pkg("LoadTills"), exec_pkg("LoadOnline"), exec_pkg("LoadCommissary"), exec_pkg("LoadAdjustments"),
         sql_task("SQL Run nightly", "EXEC dw.usp_RunNightly @BusinessDate = ?"),
         sql_task("SQL Month end", "IF DAY(GETDATE()) = 1 EXEC dw.usp_RunPeriod ?, ?")],
        [("EPT LoadTills", "SQL Run nightly"), ("EPT LoadOnline", "SQL Run nightly"),
         ("EPT LoadCommissary", "SQL Run nightly"), ("EPT LoadAdjustments", "SQL Run nightly"),
         ("SQL Run nightly", "SQL Month end")])

print(f"SliceDW: {len(daily)} legacy store-days, {len(legacy_royalty)} royalty invoices, {len(legacy_food)} food cost rows")
