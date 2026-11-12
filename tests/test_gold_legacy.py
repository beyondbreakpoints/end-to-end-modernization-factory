import ast
from calendar import monthrange
from collections import defaultdict
import csv
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import json
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from pyspark.sql import SparkSession, functions as F

from test_silver_menu_mapping import ROOT, SOURCE, notebook_cells, run_notebook


LEGACY = ROOT / "data" / "2_legacy_warehouse_slicedw"
D = Decimal
START, END = date(2026, 3, 9), date(2026, 3, 13)


def csv_rows(path, delimiter=","):
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file, delimiter=delimiter))


def sql_reference(table):
    sql = (LEGACY / "sql" / "03_reference_data.sql").read_text(encoding="utf-8-sig")
    block = re.search(rf"INSERT INTO {re.escape(table)} \([^)]+\) VALUES\n(.*?);", sql, re.S)
    rows = []
    for line in block[1].splitlines():
        value = re.sub(r"\bN'", "'", line.rstrip(","))
        value = re.sub(r"\bNULL\b", "None", value)
        rows.append(ast.literal_eval(value))
    return rows


def source_baseline():
    """Independent Python/Decimal evaluation of the legacy SQL against raw extracts."""
    mh = [r for p in sorted((SOURCE / "micros").glob("check_header_*.txt")) for r in csv_rows(p, "|")]
    md = [r for p in sorted((SOURCE / "micros").glob("check_detail_*.txt")) for r in csv_rows(p, "|")]
    ac = [r for p in sorted((SOURCE / "aloha").glob("*/*/CHECKS.csv")) for r in csv_rows(p)]
    ai = [r for p in sorted((SOURCE / "aloha").glob("*/*/ITEMS.csv")) for r in csv_rows(p)]
    orders = []
    for path in sorted((SOURCE / "online_app").glob("orders_*.json")):
        with path.open() as file:
            orders.extend(json.load(file, parse_float=D))
    menu = {int(r["micros_item_no"]): r["sku"] for r in csv_rows(SOURCE / "master_data" / "menu.csv")}
    aloha_map = {r[0]: r[1] for r in sql_reference("cfg.AlohaItemMap")}
    stores = csv_rows(SOURCE / "master_data" / "stores.csv")
    in_period = lambda day: START <= day <= END
    us_date = lambda text: datetime.strptime(text, "%m/%d/%Y %H:%M").date()
    facts, lines, online = [], [], []
    for h in mh:
        day = date.fromisoformat(h["business_date"])
        if in_period(day) and h["void_flag"] == "N":
            facts.append(dict(store_id=int(h["store"]), business_date=day, source_system="MICROS",
                              check_id=h["check_no"], gross=D(h["subtotal"]), discount=D(h["discount"]),
                              tax=D(h["tax"]), net_sales=D(h["subtotal"]) - D(h["discount"]),
                              tender=h["tender"]))
    for c in ac:
        day = us_date(c["CLOSETIME"])
        if in_period(day):
            facts.append(dict(store_id=int(c["STORE"]), business_date=day, source_system="ALOHA",
                              check_id=c["DOB"] + "-" + c["CHECKID"], gross=D(c["GROSS"]),
                              discount=D(c["COMP"]), tax=D(c["TAXINCL"]), net_sales=D(c["NETTOTAL"]),
                              tender=c["PAYTYPE"]))
    for r in md:
        day = date.fromisoformat(r["business_date"])
        if in_period(day) and r["line_type"] in ("ITEM", "GIFT"):
            lines.append((int(r["store"]), menu.get(int(r["item_no"])), int(r["qty"])))
    close_dates = {(c["STORE"], c["DOB"], c["CHECKID"]): us_date(c["CLOSETIME"]) for c in ac}
    for r in ai:
        day = close_dates[(r["STORE"], r["DOB"], r["CHECKID"])]
        if in_period(day) and r["TYPE"] == "ITEM":
            lines.append((int(r["STORE"]), aloha_map.get(r["ITEMCODE"]), int(r["QTY"])))
    micros_keys = {(f["store_id"], f["business_date"], f["check_id"]) for f in facts
                   if f["source_system"] == "MICROS"}
    for o in orders:
        day = date.fromisoformat(o["placed_at"][:10])
        if in_period(day) and o["status"] != "refunded":
            duplicate = o["pos_check_no"] is not None and (
                o["store_id"], day, str(o["pos_check_no"])) in micros_keys
            online.append(dict(store_id=o["store_id"], business_date=day, order_id=o["order_id"],
                               net_sales=D(o["subtotal"]) - D(o["discount"]),
                               is_duplicate_of_pos=duplicate, status=o["status"]))
    daily = {}
    for store, day in {(f["store_id"], f["business_date"]) for f in facts + online}:
        tills = [f for f in facts if (f["store_id"], f["business_date"]) == (store, day)]
        app = [o for o in online if (o["store_id"], o["business_date"]) == (store, day)
               and not o["is_duplicate_of_pos"]]
        amount = lambda name: sum((f[name] for f in tills), D(0))
        daily[(store, day)] = dict(
            gross_sales=amount("gross"), discounts=amount("discount"),
            voids=-sum((D(h["subtotal"]) for h in mh if int(h["store"]) == store
                        and h["business_date"] == day.isoformat() and h["void_flag"] == "V"), D(0)),
            net_sales_tills=amount("net_sales"),
            online_only_sales=sum((o["net_sales"] for o in app), D(0)),
            net_sales=amount("net_sales") + sum((o["net_sales"] for o in app), D(0)),
            tax=amount("tax"), check_count=len(tills),
            tender_list=",".join(sorted({f["tender"] for f in tills})))
    promo = defaultdict(lambda: D(0))
    for r in md:
        day = date.fromisoformat(r["business_date"])
        if in_period(day) and r["line_type"] == "DISC":
            name = {"9001": "2FOR1TUE", "9002": "WELCOME10"}.get(r["item_no"], "STAFF50")
            promo[(int(r["store"]), day, name)] -= D(r["line_amount"])
    for r in ai:
        day = us_date(r["ORDERTIME"])
        if in_period(day) and r["TYPE"] == "COMP":
            name = "2FOR1TUE" if r["ITEMCODE"] == "2F1TUE" else "STAFF50"
            promo[(int(r["STORE"]), day, name)] -= D(r["AMOUNT"])
    adjustments = csv_rows(LEGACY / "ManualAdjustments_March2026.csv")
    r2 = lambda x: x.quantize(D("0.01"), rounding=ROUND_HALF_UP)
    terms = {r[0]: D(str(r[1])) for r in sql_reference("cfg.RoyaltyTerm")}
    royalty = {}
    for s in stores:
        st = int(s["store_id"])
        if s["ownership"] != "FRANCHISE" or s["open_date"] > "2025-12-13":
            continue
        net = sum((v["net_sales"] for (store, _), v in daily.items() if store == st), D(0))
        adj = sum((D(a["Amount"]) for a in adjustments if int(a["Store"]) == st
                   and in_period(date.fromisoformat(a["Date"]))), D(0))
        roy, ad = r2(net * terms["ROYALTY_RATE"]), r2(net * terms["AD_FUND_RATE"])
        royalty[(st, START, END)] = dict(
            franchisee_id=s["franchisee_id"], franchisee_name=s["franchisee_name"],
            net_sales=net, royalty=roy, ad_fund=ad, adjustments=adj, amount_due=roy + ad + adj)
    item = {}
    for raw in (SOURCE / "as400_commissary" / "ITEMMAST.TXT").read_text().splitlines():
        item[raw[:8]] = (D(raw[32:39]) / 1000, D(raw[39:46]) / 100)
    received, theoretical = defaultdict(lambda: D(0)), defaultdict(lambda: D(0))
    for path in (SOURCE / "as400_commissary").glob("SHP*.TXT"):
        for raw in path.read_text().splitlines():
            day = date(1900 + int(raw[5]) * 100 + int(raw[6:8]), int(raw[8:10]), int(raw[10:12]))
            if in_period(day):
                received[(int(raw[:5]), raw[12:20])] += D(raw[40:47]) / 100 * item[raw[12:20]][0]
    recipes = defaultdict(list)
    for r in csv_rows(SOURCE / "master_data" / "recipes.csv"):
        recipes[r["sku"]].append((r["ingredient_item_code"], D(r["qty_per_unit"])))
    for st, sku, qty in lines:
        for code, per in recipes[sku]:
            theoretical[(st, code)] += per * qty
    counts = {}
    for path in (SOURCE / "as400_commissary").glob("CNT*.TXT"):
        for raw in path.read_text().splitlines():
            counts[(int(raw[:5]), raw[13:21], raw[12])] = D(raw[21:29]) / 1000
    food = {}
    for (st, code, kind), opening in counts.items():
        if kind != "O":
            continue
        closing, rec, theo = counts[(st, code, "C")], received[(st, code)], theoretical[(st, code)]
        actual = opening + rec - closing
        var = actual - theo
        food[(st, START, END, code)] = dict(
            opening_qty=opening, received_qty=rec, closing_qty=closing, actual_usage=actual,
            theoretical_usage=theo, variance=var,
            variance_pct=(var / theo * 100).quantize(D("0.1"), rounding=ROUND_HALF_UP) if theo else None,
            variance_cost=r2(var * item[code][1] / item[code][0]))
    org = {r[0]: r for r in sql_reference("cfg.OrgUnit")}
    region = defaultdict(lambda: D(0))
    for (st, day), values in daily.items():
        unit = st
        while unit is not None:
            region[(unit, day)] += values["net_sales"]
            unit = org[unit][1]
    return dict(daily=daily, promo=promo, royalty=royalty, food=food, region=region,
                facts=facts, lines=lines, online=online)


def corrected_source_baseline():
    """Corrected results from raw exports, independent of notebook/Silver calculations."""
    r2 = lambda x: x.quantize(D("0.01"), rounding=ROUND_HALF_UP)
    mh = [r for p in sorted((SOURCE / "micros").glob("check_header_*.txt")) for r in csv_rows(p, "|")]
    md = [r for p in sorted((SOURCE / "micros").glob("check_detail_*.txt")) for r in csv_rows(p, "|")]
    ac = [r for p in sorted((SOURCE / "aloha").glob("*/*/CHECKS.csv")) for r in csv_rows(p)]
    ai = [r for p in sorted((SOURCE / "aloha").glob("*/*/ITEMS.csv")) for r in csv_rows(p)]
    menu = {r["micros_item_no"]: r["sku"] for r in csv_rows(SOURCE / "master_data" / "menu.csv")}
    code_map = {
        "SMPEP": "PZ-PEP-S", "MDPEP": "PZ-PEP-M", "LGPEP": "PZ-PEP-L",
        "MDMARG": "PZ-MAR-M", "LGMARG": "PZ-MAR-L", "MDHAW": "PZ-HAW-M", "LGHAW": "PZ-HAW-L",
        "MDVEG": "PZ-VEG-M", "LGVEG": "PZ-VEG-L", "MDMEAT": "PZ-MTL-M", "LGMEAT": "PZ-MTL-L",
        "LGBBQ": "PZ-BBQ-L", "GARBRD": "SD-GARLIC", "WING10": "SD-WING10", "CAESAR": "SD-CAESAR",
        "DIPGAR": "SD-DIP", "CINN": "DS-CINN", "POP2L": "BV-POP2L", "POPCAN": "BV-POPCAN",
    }
    key = lambda r: (int(r["store"]), date.fromisoformat(r["business_date"]), r["check_no"])
    akey = lambda r: (int(r["STORE"]), datetime.strptime(r["DOB"], "%Y%m%d").date(), r["CHECKID"])
    voided = {key(r) for r in mh if r["void_flag"] == "V"}
    headers = {key(r): r for r in mh if r["void_flag"] == "N" and r["order_type"] != "GIFT"
               and key(r) not in voided}
    micros_lines = {(*key(r), r["line_no"], r["line_type"]): r for r in md
                    if key(r) in headers and r["line_type"] in ("ITEM", "DISC")}
    promos = defaultdict(lambda: D(0))
    comp_by_check = defaultdict(lambda: D(0))
    for r in micros_lines.values():
        if r["line_type"] == "DISC":
            st, day, _ = key(r)
            name = {"9001": "2FOR1TUE", "9002": "WELCOME10", "9003": "STAFF50"}[r["item_no"]]
            promos[(st, day, name)] -= D(r["line_amount"])
    for r in ai:
        if r["TYPE"] == "COMP":
            st, day, _ = akey(r)
            discount = r2(-D(r["AMOUNT"]) / D("1.13"))
            comp_by_check[akey(r)] += discount
            promos[(st, day, {"2F1TUE": "2FOR1TUE", "EMP50": "STAFF50"}[r["ITEMCODE"]])] += discount
    facts = {}
    for k, r in headers.items():
        st, day, check = k
        gross, discount = D(r["subtotal"]), D(r["discount"])
        facts[("MICROS", f"{st}|{day:%Y%m%d}|{check}")] = dict(
            store_id=st, business_date=day, gross=gross, discount=discount, net_sales=gross-discount,
            tax=D(r["tax"]), tip=D(r["tip"]), total=D(r["total"]),
            is_online=r["tender"] == "WEB", tender=r["tender"])
    for r in ac:
        st, day, check = akey(r)
        net, discount = D(r["NETTOTAL"]) - D(r["TAXINCL"]), comp_by_check[akey(r)]
        facts[("ALOHA", f"{st}|{day:%Y%m%d}|{check}")] = dict(
            store_id=st, business_date=day, gross=net+discount, discount=discount, net_sales=net,
            tax=D(r["TAXINCL"]), tip=D(r["TIP"]), total=D(r["TOTAL"]),
            is_online=r["PAYTYPE"] == "WEB", tender=r["PAYTYPE"])
    daily = {}
    for st, day in {(v["store_id"], v["business_date"]) for v in facts.values()}:
        rows = [v for v in facts.values() if (v["store_id"], v["business_date"]) == (st, day)]
        amount = lambda c: sum((v[c] for v in rows), D(0))
        daily[(st, day)] = dict(gross_sales=amount("gross"), discounts=amount("discount"),
            net_sales=amount("net_sales"), tax=amount("tax"), tips=amount("tip"), check_count=len(rows),
            online_pos_net_sales=sum((v["net_sales"] for v in rows if v["is_online"]), D(0)),
            tender_list=",".join(sorted({v["tender"] for v in rows})))
    sold = defaultdict(lambda: D(0))
    lines = {}
    for r in micros_lines.values():
        if r["line_type"] == "ITEM":
            st, day, check = key(r)
            sku, qty = menu[r["item_no"]], int(r["qty"])
            lines[("MICROS", f"{st}|{day:%Y%m%d}|{check}", int(r["line_no"]))] = dict(sku=sku, qty=qty)
            sold[(st, sku)] += qty
    for r in ai:
        if r["TYPE"] == "ITEM":
            st, day, check = akey(r)
            sku, qty = code_map[r["ITEMCODE"]], int(r["QTY"])
            lines[("ALOHA", f"{st}|{day:%Y%m%d}|{check}", int(r["ENTRYID"]))] = dict(sku=sku, qty=qty)
            sold[(st, sku)] += qty
    adj = {}
    for r in csv_rows(LEGACY / "ManualAdjustments_March2026.csv"):
        adj.setdefault((int(r["Store"]), r["Date"], r["Type"], r["Amount"], r["Note"]), D(r["Amount"]))
    terms = {r[0]: D(str(r[1])) for r in sql_reference("cfg.RoyaltyTerm")}
    royalty = {}
    for s in csv_rows(SOURCE / "master_data" / "stores.csv"):
        opened = date.fromisoformat(s["open_date"])
        year, month = divmod(opened.year*12+opened.month-1+int(terms["NEW_STORE_HOLIDAY_MONTHS"]), 12)
        eligible = date(year, month+1, min(opened.day, monthrange(year, month+1)[1]))
        if s["ownership"] != "FRANCHISE" or eligible > END:
            continue
        st = int(s["store_id"])
        net = sum((v["net_sales"] for (store, _), v in daily.items() if store == st), D(0))
        adjustment = sum((v for k, v in adj.items() if k[0] == st and START.isoformat() <= k[1] <= END.isoformat()), D(0))
        roy, ad = r2(net*terms["ROYALTY_RATE"]), r2(net*terms["AD_FUND_RATE"])
        royalty[(st, START, END)] = dict(franchisee_id=s["franchisee_id"], franchisee_name=s["franchisee_name"],
            net_sales=net, royalty=roy, ad_fund=ad, adjustments=adjustment, amount_due=roy+ad+adjustment)
    item = {}
    for raw in (SOURCE / "as400_commissary" / "ITEMMAST.TXT").read_text().splitlines():
        item[raw[:8]] = (D(raw[32:39])/1000, D(raw[39:46])/100, raw[30:32].strip())
    received = defaultdict(lambda: D(0))
    for path in (SOURCE / "as400_commissary").glob("SHP*.TXT"):
        for raw in path.read_text().splitlines():
            qty, code = D(raw[40:47])/100, raw[12:20]
            if raw[47:49] == "CS":
                qty *= item[code][0]
            received[(int(raw[:5]), code)] += -qty if raw[-1] == "-" else qty
    theoretical = defaultdict(lambda: D(0))
    for r in csv_rows(SOURCE / "master_data" / "recipes.csv"):
        for (st, sku), qty in sold.items():
            if sku == r["sku"]:
                theoretical[(st, r["ingredient_item_code"])] += qty * D(r["qty_per_unit"])
    counts = {}
    for path in (SOURCE / "as400_commissary").glob("CNT*.TXT"):
        for raw in path.read_text().splitlines():
            counts[(int(raw[:5]), raw[13:21], raw[12])] = D(raw[21:29])/1000
    food = {}
    for (st, code, kind), opening in counts.items():
        if kind != "O":
            continue
        rec, closing, theo = received[(st, code)], counts[(st, code, "C")], theoretical[(st, code)]
        actual = opening+rec-closing
        var = actual-theo
        food[(st, START, END, code)] = dict(base_uom=item[code][2], opening_qty=opening, received_qty=rec,
            closing_qty=closing, actual_usage=actual, theoretical_usage=theo, variance=var,
            variance_pct=(var/theo*100).quantize(D("0.1"), rounding=ROUND_HALF_UP) if theo else None,
            variance_cost=r2(var*item[code][1]/item[code][0]))
    org = {r[0]: r for r in sql_reference("cfg.OrgUnit")}
    region = defaultdict(lambda: D(0))
    for (st, day), values in daily.items():
        unit = st
        while unit is not None:
            region[(unit, day)] += values["net_sales"]
            unit = org[unit][1]
    return dict(facts=facts, lines=lines, daily=daily, promo=promos, royalty=royalty, food=food, region=region)


class GoldLegacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = TemporaryDirectory(prefix="gold-legacy-tests-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.spark = (SparkSession.builder.master("local[2]").appName("gold-legacy-tests")
                     .config("spark.sql.warehouse.dir", cls.workspace.name)
                     .config("spark.sql.shuffle.partitions", "2")
                     .config("spark.ui.enabled", "false")
                     .config("spark.sql.session.timeZone", "UTC")
                     .getOrCreate())
        cls.addClassCleanup(cls.spark.stop)
        cls.spark.sparkContext.setLogLevel("ERROR")
        cls.tables = {}
        for stem in ("stores", "menu", "calendar", "recipes"):
            df = cls.spark.read.option("header", "true").csv(str(SOURCE / "master_data" / f"{stem}.csv"))
            cls.tables[f"bronze.master_{stem}"] = cls.meta(df)
        for prefix in ("check_header", "check_detail"):
            df = cls.spark.read.option("header", "true").option("sep", "|").csv(
                str(SOURCE / "micros" / f"{prefix}_*.txt"))
            cls.tables[f"bronze.micros_{prefix}"] = cls.meta(df)
        for filename, table in (("CHECKS.csv", "aloha_checks"), ("ITEMS.csv", "aloha_items")):
            df = cls.spark.read.option("header", "true").csv(
                [str(p) for p in sorted((SOURCE / "aloha").glob(f"*/*/{filename}"))])
            cls.tables[f"bronze.{table}"] = cls.meta(df)
        layouts = {
            "as400_itemmast": ("ITEMMAST.TXT", [
                ("item_code", 0, 8), ("item_desc", 8, 20), ("pack_uom", 28, 2),
                ("base_uom", 30, 2), ("pack_qty", 32, 7), ("pack_cost", 39, 7), ("status", 46, 1)]),
            "as400_shipments": ("SHP*.TXT", [
                ("store_no", 0, 5), ("ship_date", 5, 7), ("item_code", 12, 8),
                ("item_desc", 20, 20), ("qty", 40, 7), ("uom", 47, 2), ("ext_cost", 49, 10)]),
            "as400_counts": ("CNT*.TXT", [
                ("store_no", 0, 5), ("count_date", 5, 7), ("count_type", 12, 1),
                ("item_code", 13, 8), ("qty_on_hand", 21, 8), ("base_uom", 29, 2)]),
        }
        for table, (pattern, fields) in layouts.items():
            rows = []
            for path in sorted((SOURCE / "as400_commissary").glob(pattern)):
                for raw in path.read_text().splitlines():
                    rows.append(dict({n: raw[s:s + size] for n, s, size in fields},
                                     _source_file=str(path)))
            cls.tables[f"bronze.{table}"] = cls.meta(cls.spark.createDataFrame(rows))
        order_rows, item_rows = [], []
        for path in sorted((SOURCE / "online_app").glob("orders_*.json")):
            with path.open() as file:
                orders = json.load(file)
            for o in orders:
                row = {k: None if v is None else str(v) for k, v in o.items() if k not in ("customer", "items")}
                row.update({f"customer_{k}": str(o["customer"][v])
                            for k, v in (("id", "id"), ("name", "name"), ("email", "email"), ("phone", "phone"))})
                order_rows.append(row)
                for line, item in enumerate(o["items"], 1):
                    item_rows.append(dict(order_id=o["order_id"], line_no=str(line),
                                          **{k: str(v) for k, v in item.items()}))
        cls.tables["bronze.online_orders"] = cls.meta(cls.spark.createDataFrame(order_rows))
        cls.tables["bronze.online_order_items"] = cls.meta(cls.spark.createDataFrame(item_rows))
        cls.tables["bronze.online_customers"] = cls.meta(
            cls.spark.read.option("header", "true").csv(str(SOURCE / "online_app" / "customers.csv")))
        for system in ("master_data", "micros", "aloha", "as400_commissary", "online_app"):
            run_notebook(f"nb_silver_{system}", cls.spark, cls.tables, {"batch_id": "silver-fixture"})
        cls.execute_gold("nb_gold_reference_data")
        cls.execute_gold("nb_gold_legacy")
        cls.baseline = source_baseline()
        cls.execute_gold("nb_gold_corrected", {"batch_id": "corrected-fixture"})
        cls.corrected_baseline = corrected_source_baseline()

    @staticmethod
    def meta(df):
        for col in ("_source_system", "_source_file", "_file_modified", "_ingest_ts", "_batch_id"):
            if col not in df.columns:
                df = df.withColumn(col, F.lit("fixture"))
        return df

    @classmethod
    def execute_gold(cls, name, parameters=None):
        def table(name):
            return cls.tables[name] if name in cls.tables else cls.spark.table(name)
        namespace = {"spark": SimpleNamespace(
            table=table, sql=cls.spark.sql, createDataFrame=cls.spark.createDataFrame)}
        for cell in notebook_cells(name):
            # Exercise real Spark SQL, validations, and table writes without requiring Fabric Delta jars.
            exec(compile(cell.replace('format("delta")', 'format("parquet")'), name, "exec"), namespace)
            if cell.startswith("# PARAMETERS CELL "):
                namespace.update({"batch_id": "gold-fixture", **(parameters or {})})
        return namespace

    def assert_report(self, table, keys, expected):
        rows = self.spark.table(f"gold.{table}").collect()
        actual = {tuple(row[k] for k in keys): row.asDict() for row in rows}
        self.assertEqual(len(actual), len(rows), table)
        self.assertEqual(set(actual), set(expected), table)
        for key, values in expected.items():
            for col, value in values.items():
                self.assertEqual(actual[key][col], value, f"{table} {key} {col}")

    def test_every_legacy_report_matches_independent_raw_source_baseline(self):
        b = self.baseline
        self.assert_report("legacy_daily_sales", ("store_id", "business_date"), b["daily"])
        self.assert_report("legacy_promo_cost", ("store_id", "business_date", "promo_name"),
                           {k: {"discount_amount": v} for k, v in b["promo"].items()})
        self.assert_report("legacy_royalty_invoices", ("store_id", "period_start", "period_end"), b["royalty"])
        self.assert_report("legacy_food_cost_variance",
                           ("store_id", "period_start", "period_end", "item_code"), b["food"])
        self.assert_report("legacy_region_daily_sales", ("unit_id", "business_date"),
                           {k: {"net_sales": v} for k, v in b["region"].items()})
        franchisees = {}
        for (_, ps, pe), r in b["royalty"].items():
            key = (r["franchisee_id"], ps, pe)
            if key not in franchisees:
                franchisees[key] = {c: D(0) for c in (
                    "net_sales", "royalty", "ad_fund", "adjustments", "amount_due")}
                franchisees[key].update(stores=0, franchisee_name=r["franchisee_name"])
            franchisees[key]["stores"] += 1
            for c in ("net_sales", "royalty", "ad_fund", "adjustments", "amount_due"):
                franchisees[key][c] += r[c]
        self.assert_report("legacy_franchisee_invoices",
                           ("franchisee_id", "period_start", "period_end"), franchisees)
        by_day = {}
        for f in b["facts"]:
            key = (f["store_id"], f["business_date"], f["source_system"])
            by_day.setdefault(key, dict(net_sales=D(0), tax=D(0), check_count=0))
            for c in ("net_sales", "tax"):
                by_day[key][c] += f[c]
            by_day[key]["check_count"] += 1
        self.assert_report("legacy_store_day_sales", ("store_id", "business_date", "source_system"), by_day)

    def test_reference_snapshots_match_legacy_sql_and_preserve_duplicate_credit(self):
        for table, source, cols in [
            ("reference_legacy_aloha_map", "cfg.AlohaItemMap", ("aloha_item_code", "sku")),
            ("reference_org_units", "cfg.OrgUnit",
             ("unit_id", "parent_unit_id", "unit_name", "unit_type", "store_id")),
            ("reference_royalty_terms", "cfg.RoyaltyTerm", ("term_code", "term_value", "note")),
        ]:
            actual = {tuple(r[c] for c in cols) for r in self.spark.table(f"gold.{table}").collect()}
            expected = {tuple(r[:len(cols)]) for r in sql_reference(source)}
            if source == "cfg.RoyaltyTerm":
                expected = {(r[0], D(str(r[1])), r[2]) for r in sql_reference(source)}
            self.assertEqual(actual, expected)
        adjustments = self.spark.table("gold.reference_manual_adjustments")
        actual = [(r.store_id, r.business_date.isoformat(), r.adj_type, r.amount,
                   r.note, r.keyed_by, r.keyed_at.isoformat()) for r in adjustments.orderBy("adjustment_id").collect()]
        expected = [(r[0], r[1], r[2], D(str(r[3])), r[4], r[5], r[6])
                    for r in sql_reference("adj.ManualAdjustment")]
        self.assertEqual(actual, expected)
        self.assertEqual(adjustments.filter("is_possible_duplicate").count(), 2)

    def test_legacy_defects_are_not_silently_corrected(self):
        facts = self.spark.table("gold.legacy_fact_checks")
        self.assertEqual(facts.count(), len(self.baseline["facts"]))
        self.assertEqual(facts.filter("order_type = 'GIFT'").count(), 49)
        self.assertGreater(facts.groupBy("store_id", "business_date", "source_system", "check_id")
                           .count().filter("count > 1").count(), 0)
        lines = self.spark.table("gold.legacy_fact_check_lines")
        self.assertEqual(lines.count(), len(self.baseline["lines"]))
        self.assertEqual({r.sku for r in lines.filter("source_system = 'ALOHA' AND source_item_code = 'MDVEG'")
                          .select("sku").distinct().collect()}, {"PZ-VEG-L"})
        self.assertGreater(lines.filter("source_system = 'ALOHA' AND sku IS NULL").count(), 0)
        online = self.spark.table("gold.legacy_fact_online_orders")
        self.assertEqual(online.filter("status = 'cancelled'").count(), 34)
        self.assertEqual(online.filter("is_duplicate_of_pos").count(), 1637)
        self.assertEqual(self.spark.table("gold.legacy_royalty_invoices").filter("store_id = 1078").count(), 1)
        manifest = self.spark.table("gold.legacy_run_inputs")
        self.assertEqual(manifest.count(), 16)

    def test_period_snapshot_filters_reports_but_keeps_all_commissary_extracts(self):
        try:
            self.execute_gold("nb_gold_legacy", {"period_start": "2026-03-10", "period_end": "2026-03-12"})
            days = {r.business_date for r in self.spark.table("gold.legacy_daily_sales").collect()}
            self.assertEqual(days, {date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)})
            self.assertEqual(self.spark.table("gold.legacy_shipments").count(), 564)
            self.assertEqual(self.spark.table("gold.legacy_stock_counts").count(), 380)
            self.assertEqual(self.spark.table("gold.legacy_food_cost_variance").count(), 0)
        finally:
            self.execute_gold("nb_gold_legacy")

    def test_rerun_is_idempotent_and_mixed_silver_batches_are_rejected(self):
        before = self.spark.table("gold.legacy_daily_sales").orderBy("store_id", "business_date").collect()
        self.execute_gold("nb_gold_legacy")
        after = self.spark.table("gold.legacy_daily_sales").orderBy("store_id", "business_date").collect()
        self.assertEqual(before, after)
        original = self.tables["silver.menu"]
        self.tables["silver.menu"] = original.withColumn("_silver_batch_id", F.lit("different-batch"))
        try:
            with self.assertRaisesRegex(AssertionError, "Silver inputs must come from one"):
                self.execute_gold("nb_gold_legacy")
        finally:
            self.tables["silver.menu"] = original

    def test_corrected_reports_match_independent_source_baseline(self):
        b = self.corrected_baseline
        self.assert_report("corrected_fact_checks", ("source_system", "check_key"), b["facts"])
        self.assert_report("corrected_fact_check_lines", ("source_system", "check_key", "line_no"), b["lines"])
        self.assert_report("corrected_daily_sales", ("store_id", "business_date"), b["daily"])
        self.assert_report("corrected_promo_cost", ("store_id", "business_date", "promo_name"),
                           {k: {"discount_amount": v} for k, v in b["promo"].items()})
        self.assert_report("corrected_royalty_invoices", ("store_id", "period_start", "period_end"), b["royalty"])
        self.assert_report("corrected_food_cost_variance", ("store_id", "period_start", "period_end", "item_code"), b["food"])
        self.assert_report("corrected_region_daily_sales", ("unit_id", "business_date"),
                           {k: {"net_sales": v} for k, v in b["region"].items()})
        franchisees = {}
        for (_, ps, pe), r in b["royalty"].items():
            k = (r["franchisee_id"], ps, pe)
            row = franchisees.setdefault(k, dict(stores=0, **{
                c: D(0) for c in ("net_sales", "royalty", "ad_fund", "adjustments", "amount_due")}))
            row["stores"] += 1
            for c in ("net_sales", "royalty", "ad_fund", "adjustments", "amount_due"):
                row[c] += r[c]
        self.assert_report("corrected_franchisee_invoices", ("franchisee_id", "period_start", "period_end"), franchisees)
        invoices = self.spark.table("gold.corrected_royalty_invoices")
        self.assertEqual(invoices.filter("store_id = 1078").count(), 0)
        self.assertEqual(invoices.filter("store_id = 1055").first().adjustments, D("-120"))
        decisions = self.spark.table("gold.corrected_adjustment_decisions")
        self.assertEqual({r.adjustment_id: r.is_included for r in decisions.collect()},
                         {1: True, 2: True, 3: True, 4: False, 5: True})
        attribution = self.spark.table("gold.corrected_online_attribution")
        statuses = {r.attribution_status: r["count"] for r in attribution.groupBy("attribution_status").count().collect()}
        self.assertEqual(statuses, {"CANCELLED": 34, "MATCHED_MICROS": 1637, "MATCHED_ALOHA": 630,
                                    "AMBIGUOUS_ALOHA": 1})
        self.assertEqual(attribution.filter("incremental_net_sales <> 0").count(), 0)
        ambiguous = attribution.filter("attribution_status = 'AMBIGUOUS_ALOHA'").first()
        self.assertIsNone(ambiguous.attributed_check_key)
        self.assertIsNone(ambiguous.attributed_net_sales)
        cancelled = attribution.filter("attribution_status = 'CANCELLED'")
        self.assertEqual(cancelled.filter("attributed_check_key IS NOT NULL").count(), 0)

    def test_corrected_rerun_preserves_legacy_references_and_own_results(self):
        preserved = {t: self.spark.table(f"gold.{t}").collect() for t in
                     ("legacy_daily_sales", "legacy_royalty_invoices", "legacy_run_inputs",
                      "reference_manual_adjustments", "reference_royalty_terms")}
        outputs = [r.tableName for r in self.spark.sql("SHOW TABLES IN gold").collect()
                   if r.tableName.startswith("corrected_")]
        before = {t: sorted(self.spark.table(f"gold.{t}").collect(), key=repr) for t in outputs}
        self.execute_gold("nb_gold_corrected", {"batch_id": "corrected-fixture"})
        for table, rows in before.items():
            self.assertEqual(rows, sorted(self.spark.table(f"gold.{table}").collect(), key=repr), table)
        for table, rows in preserved.items():
            self.assertEqual(rows, self.spark.table(f"gold.{table}").collect(), table)

    def test_corrected_preflight_rejects_mixed_batches_conflicts_and_missing_counts(self):
        cases = [
            ("silver.menu", lambda df: df.withColumn("_silver_batch_id", F.lit("other")),
             "Mixed silver"),
            ("silver.micros_checks", lambda df: df.unionByName(
                df.limit(1).withColumn("subtotal", F.col("subtotal")+1)), "conflicting versions"),
            ("silver.as400_stock_counts", lambda df: df.filter("NOT (store_id = 1042 AND count_type = 'O')"),
             "Missing O stock counts"),
        ]
        for table, alter, message in cases:
            original = self.tables[table]
            with self.subTest(table=table):
                try:
                    self.tables[table] = alter(original)
                    with self.assertRaisesRegex(AssertionError, message):
                        self.execute_gold("nb_gold_corrected")
                finally:
                    self.tables[table] = original
        with self.assertRaisesRegex(AssertionError, "Missing O stock counts"):
            self.execute_gold("nb_gold_corrected", {"period_start": "2026-03-10"})


if __name__ == "__main__":
    unittest.main()
