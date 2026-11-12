"""Generates NCR Aloha daily export files for the Aloha stores (acquired in 2022), plus answer-key files.

Output (under <out>/):
  aloha/<store>/<YYYYMMDD>/CHECKS.csv   one row per check; amounts INCLUDE tax
  aloha/<store>/<YYYYMMDD>/ITEMS.csv    one row per item or comp line
  answer_key/aloha_*.csv
Differences from MICROS, on purpose: tax-inclusive prices, a 4 a.m. business-day cut-off (DOB),
US-style timestamps, check numbers that restart every day, short item codes, and online orders
that carry no online order ID.
"""
import csv, os, random, sys
from datetime import datetime, time, timedelta
from decimal import Decimal
from common import P, SEED, STORES, MENU, HST, business_dates, money

OUT = sys.argv[1] if len(sys.argv) > 1 else ".."
rng = random.Random(SEED + 2)

CHECK_COLS = ["STORE", "DOB", "CHECKID", "TABLENUM", "ORDERMODE", "OPENTIME", "CLOSETIME", "GROSS", "COMP",
              "NETTOTAL", "TAXINCL", "TIP", "TOTAL", "PAYTYPE", "EMPLOYEE"]
ITEM_COLS = ["STORE", "DOB", "CHECKID", "ENTRYID", "ITEMCODE", "ITEMNAME", "QTY", "PRICE", "AMOUNT", "TYPE", "ORDERTIME"]

BASE_CHECKS = {0: 150, 1: 230, 2: 160, 3: 175, 4: 260, 5: 280, 6: 220}
# Hour of the business day; 24 and 25 mean 00:xx and 01:xx after midnight (still the same DOB)
HOUR_WEIGHTS = {11: 4, 12: 9, 13: 6, 14: 3, 15: 3, 16: 5, 17: 10, 18: 13, 19: 11, 20: 7, 21: 5, 22: 4, 23: 3, 24: 2, 25: 1}
PIZZAS = [m for m in MENU if m[2] == "PIZZA"]
OTHERS = [m for m in MENU if m[2] != "PIZZA"]
COMP_2F1 = ("2F1TUE", "2F1 TUES")
COMP_STAFF = ("EMP50", "EMP 50%")


def incl(price_excl):
    return money(Decimal(price_excl) * (1 + HST))


def ts(dt):
    return dt.strftime("%m/%d/%Y %H:%M")


def pick_items(is_tuesday):
    items = {}
    n_pizzas = rng.choices([1, 2, 3, 4], weights=[45, 35, 15, 5] if not is_tuesday else [20, 50, 20, 10])[0]
    for _ in range(n_pizzas):
        if is_tuesday and rng.random() < 0.55:
            larges = [m for m in PIZZAS if m[3] == "L"]
            p = rng.choices(larges, weights=[m[9] for m in larges])[0]
        else:
            p = rng.choices(PIZZAS, weights=[m[9] for m in PIZZAS])[0]
        items[p] = items.get(p, 0) + 1
    for _ in range(rng.choices([0, 1, 2, 3], weights=[30, 40, 22, 8])[0]):
        o = rng.choices(OTHERS, weights=[m[9] for m in OTHERS])[0]
        items[o] = items.get(o, 0) + 1
    return items


checks_by_file, items_by_file = {}, {}
control, true_rows, late_rows, online_rows = [], [], [], []

for store_row in [s for s in STORES if s[6] == "ALOHA"]:
    store, factor = store_row[0], store_row[8]
    servers = [f"S{n:03d}" for n in rng.sample(range(100, 400), 5)]
    for d in business_dates():
        dob = d.strftime("%Y%m%d")
        is_tue = d.weekday() == 1
        n = round(BASE_CHECKS[d.weekday()] * factor * rng.uniform(0.9, 1.1))
        drafts = []
        for _ in range(n):
            hour = rng.choices(list(HOUR_WEIGHTS), weights=list(HOUR_WEIGHTS.values()))[0]
            opened = datetime.combine(d, time(0)) + timedelta(hours=hour, minutes=rng.randrange(60), seconds=rng.randrange(60))
            drafts.append(opened)
        drafts.sort()

        rows_c, rows_i = [], []
        tot = {"net_excl": Decimal("0"), "net_incl": Decimal("0"), "tax": Decimal("0"), "online_excl": Decimal("0"),
               "late_excl": Decimal("0"), "late_checks": 0}
        for check_id, opened in enumerate(drafts, start=10001):
            mode = rng.choices(["DINE IN", "TO GO", "DELIVERY", "ONLINE"], weights=[25, 30, 20, 25])[0]
            closed = opened + timedelta(minutes=rng.randint(20, 55) if mode == "DINE IN" else rng.randint(2, 30))
            items = pick_items(is_tue)
            gross = Decimal("0")
            lines = []
            for m, q in items.items():
                p = incl(m[4])
                amt = p * q
                gross += amt
                lines.append([m[7], m[8], q, p, amt, "ITEM"])

            comp = Decimal("0")
            if is_tue:
                larges = sorted(incl(m[4]) for m, q in items.items() if m[3] == "L" for _ in range(q))
                comp = sum(larges[: len(larges) // 2], Decimal("0"))
                if comp:
                    lines.append([COMP_2F1[0], COMP_2F1[1], 1, -comp, -comp, "COMP"])
            elif mode in ("DINE IN", "TO GO") and rng.random() < 0.01:
                comp = money(gross * Decimal("0.5"))
                lines.append([COMP_STAFF[0], COMP_STAFF[1], 1, -comp, -comp, "COMP"])

            net_incl = gross - comp
            net_excl = money(net_incl / (1 + HST))
            tax_incl = net_incl - net_excl
            paytype = "WEB" if mode == "ONLINE" else rng.choices(
                ["VISA", "MASTERCARD", "INTERAC", "CASH", "AMEX"], weights=[30, 20, 32, 15, 3])[0]
            tip = Decimal("0")
            if mode == "DINE IN" and paytype != "CASH" and rng.random() < 0.7:
                tip = money(net_incl * Decimal(rng.choice(["0.10", "0.12", "0.15", "0.18"])))
            elif mode in ("DELIVERY", "ONLINE") and paytype != "CASH" and rng.random() < 0.45:
                tip = Decimal(rng.choice(["2.00", "3.00", "4.00", "5.00"]))
            order_mode = rng.choice(["DELIVERY", "TO GO"]) if mode == "ONLINE" else mode
            table = str(rng.randint(1, 18)) if mode == "DINE IN" else ""

            rows_c.append([store, dob, check_id, table, order_mode, ts(opened), ts(closed), gross, comp, net_incl,
                           tax_incl, tip, net_incl + tip, paytype, rng.choice(servers)])
            for entry, l in enumerate(lines, 1):
                rows_i.append([store, dob, check_id, entry] + l + [ts(opened)])

            tot["net_excl"] += net_excl
            tot["net_incl"] += net_incl
            tot["tax"] += tax_incl
            if mode == "ONLINE":
                tot["online_excl"] += net_excl
                online_rows.append([store, d.isoformat(), check_id, opened.strftime("%Y-%m-%d %H:%M:%S"), order_mode,
                                    gross, comp, net_incl, net_excl, tax_incl, tip,
                                    ";".join(f"{m[0]}x{q}" for m, q in items.items())])
            if closed.date() > d:
                tot["late_excl"] += net_excl
                tot["late_checks"] += 1
                late_rows.append([store, d.isoformat(), check_id, closed.strftime("%Y-%m-%d %H:%M"), net_excl,
                                  "Closed after midnight: belongs to the previous business day (DOB), not the calendar date"])

        checks_by_file[(store, dob)] = rows_c
        items_by_file[(store, dob)] = rows_i
        control.append([store, d.isoformat(), len(rows_c), len(rows_i)] +
                       [sum((r[i] for r in rows_c), Decimal("0")) for i in (7, 8, 9, 10, 11, 12)])
        true_rows.append([store, d.isoformat(), len(rows_c), tot["net_incl"], tot["tax"], tot["net_excl"],
                          tot["online_excl"], tot["late_checks"], tot["late_excl"]])


def fmt(v):
    return f"{v:.2f}" if isinstance(v, Decimal) else str(v)


for (store, dob), rows in checks_by_file.items():
    folder = os.path.join(OUT, P["aloha"], str(store), dob)
    os.makedirs(folder, exist_ok=True)
    for name, cols, data in (("CHECKS.csv", CHECK_COLS, rows), ("ITEMS.csv", ITEM_COLS, items_by_file[(store, dob)])):
        with open(os.path.join(folder, name), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows([[fmt(v) for v in r] for r in data])

key = os.path.join(OUT, P["answer_key"])
os.makedirs(key, exist_ok=True)
files = {
    "aloha_control_totals.csv": (["store", "business_date", "check_rows", "item_rows", "sum_gross", "sum_comp",
                                  "sum_nettotal", "sum_taxincl", "sum_tip", "sum_total"], control),
    "aloha_true_net_sales.csv": (["store", "business_date", "checks", "net_sales_incl_tax", "tax_included",
                                  "net_sales", "net_sales_from_online_orders", "checks_closed_after_midnight",
                                  "net_sales_closed_after_midnight"], true_rows),
    "aloha_planted_defects.csv": (["store", "business_date", "check_id", "closed_at", "net_sales", "description"],
                                  late_rows),
    "aloha_online_orders.csv": (["store", "business_date", "check_id", "placed_at", "order_mode", "gross_incl_tax",
                                 "comp_incl_tax", "net_incl_tax", "net_sales", "tax_included", "tip", "items"],
                                online_rows),
}
for name, (cols, data) in files.items():
    with open(os.path.join(key, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows([[fmt(v) for v in r] for r in data])

print(f"Aloha: {sum(len(v) for v in checks_by_file.values())} checks, "
      f"{sum(len(v) for v in items_by_file.values())} item rows, {len(late_rows)} after-midnight checks, "
      f"{len(online_rows)} online orders without an online ID")
