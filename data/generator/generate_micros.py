"""Generates Oracle MICROS RES 3700 nightly extract files for the MICROS stores, plus answer-key files.

Output (under <out>/):
  micros/check_header_YYYYMMDD.txt   one row per check, pipe-delimited, CRLF line endings
  micros/check_detail_YYYYMMDD.txt   one row per check line
  answer_key/micros_*.csv            control totals, true net sales, planted defects, online refs
"""
import csv, os, random, sys
from datetime import datetime, time, timedelta
from decimal import Decimal
from common import (P, SEED, STORES, MENU, HST, business_dates, money,
                    MICROS_GIFT_LOAD, MICROS_DISC_2F1, MICROS_DISC_WELCOME, MICROS_DISC_STAFF)

OUT = sys.argv[1] if len(sys.argv) > 1 else ".."
rng = random.Random(SEED + 1)

HEADER_COLS = ["store", "business_date", "check_no", "open_time", "close_time", "order_type", "guest_count",
               "subtotal", "discount", "tax", "tip", "total", "tender", "void_flag", "online_ref", "employee_id"]
DETAIL_COLS = ["store", "business_date", "check_no", "line_no", "item_no", "item_name", "qty",
               "unit_price", "line_amount", "line_type"]

BASE_CHECKS = {0: 150, 1: 230, 2: 160, 3: 175, 4: 260, 5: 280, 6: 220}   # by weekday; Tuesday is 2-for-1
HOUR_WEIGHTS = {11: 4, 12: 9, 13: 6, 14: 3, 15: 3, 16: 5, 17: 10, 18: 13, 19: 11, 20: 7, 21: 4, 22: 2}
PIZZAS = [m for m in MENU if m[2] == "PIZZA"]
OTHERS = [m for m in MENU if m[2] != "PIZZA"]
DUPLICATE_POLL = (1061, "2026-03-12", 12)   # store, date, number of checks re-sent at the end of the file

micros_stores = [s for s in STORES if s[6] == "MICROS"]
online_seq = 884000
headers, details = {}, {}            # date -> rows
defects, online_refs, true_rows = [], [], []


def pick_items(is_tuesday):
    """Returns {menu_row: qty} for one order."""
    items = {}
    n_pizzas = rng.choices([1, 2, 3, 4], weights=[45, 35, 15, 5] if not is_tuesday else [20, 50, 20, 10])[0]
    for _ in range(n_pizzas):
        if is_tuesday and rng.random() < 0.55:
            p = rng.choices([m for m in PIZZAS if m[3] == "L"], weights=[m[9] for m in PIZZAS if m[3] == "L"])[0]
        else:
            p = rng.choices(PIZZAS, weights=[m[9] for m in PIZZAS])[0]
        items[p] = items.get(p, 0) + 1
    for _ in range(rng.choices([0, 1, 2, 3], weights=[30, 40, 22, 8])[0]):
        o = rng.choices(OTHERS, weights=[m[9] for m in OTHERS])[0]
        items[o] = items.get(o, 0) + 1
    return items


def two_for_one_discount(items):
    larges = sorted(Decimal(m[4]) for m, q in items.items() if m[3] == "L" for _ in range(q))
    return sum(larges[: len(larges) // 2], Decimal("0"))


def make_sale_check(store, d, check_no, emp_ids):
    global online_seq
    is_tue = d.weekday() == 1
    channel = rng.choices(["DINE", "TAKE", "DELIV", "ONLINE"], weights=[25, 30, 20, 25])[0]
    hour = rng.choices(list(HOUR_WEIGHTS), weights=list(HOUR_WEIGHTS.values()))[0]
    opened = datetime.combine(d, time(hour, rng.randrange(60), rng.randrange(60)))
    closed = opened + timedelta(minutes=rng.randint(20, 60) if channel == "DINE" else rng.randint(2, 35),
                                seconds=rng.randrange(60))
    items = pick_items(is_tue)
    lines, subtotal = [], Decimal("0")
    for m, q in items.items():
        amt = money(Decimal(m[4]) * q)
        subtotal += amt
        lines.append([m[5], m[6], q, m[4], amt, "ITEM"])

    discount, disc_key = Decimal("0"), None
    if is_tue and two_for_one_discount(items) > 0:
        discount, disc_key = two_for_one_discount(items), MICROS_DISC_2F1
    elif channel == "ONLINE" and rng.random() < 0.04:
        discount, disc_key = money(subtotal * Decimal("0.10")), MICROS_DISC_WELCOME
    elif channel in ("DINE", "TAKE") and rng.random() < 0.01:
        discount, disc_key = money(subtotal * Decimal("0.50")), MICROS_DISC_STAFF
    if disc_key:
        lines.append([disc_key[0], disc_key[1], 1, -discount, -discount, "DISC"])

    tax = money((subtotal - discount) * HST)
    if channel == "ONLINE":
        tender = "WEB"
    else:
        tender = rng.choices(["VISA", "MC", "DEBIT", "CASH", "AMEX", "GIFTCARD"], weights=[30, 20, 30, 15, 3, 2])[0]
    tip = Decimal("0")
    if channel == "DINE" and tender not in ("CASH", "GIFTCARD") and rng.random() < 0.7:
        tip = money((subtotal - discount) * Decimal(rng.choice(["0.10", "0.12", "0.15", "0.18"])))
    elif channel in ("DELIV", "ONLINE") and tender != "CASH" and rng.random() < 0.45:
        tip = Decimal(rng.choice(["2.00", "3.00", "4.00", "5.00"]))

    online_ref = ""
    order_type = channel
    if channel == "ONLINE":
        online_seq += rng.randint(1, 9)
        online_ref = f"PS-{rng.choice(['W', 'A'])}-{online_seq}"
        order_type = rng.choice(["DELIV", "TAKE"])
    total = subtotal - discount + tax + tip
    header = [store, d.isoformat(), check_no, opened.strftime("%H:%M:%S"), closed.strftime("%H:%M:%S"),
              order_type, rng.randint(1, 5) if channel == "DINE" else 1,
              subtotal, discount, tax, tip, total, tender, "N", online_ref, rng.choice(emp_ids)]
    return header, lines, channel


def make_gift_load(store, d, check_no, emp_ids):
    opened = datetime.combine(d, time(rng.randint(11, 21), rng.randrange(60), rng.randrange(60)))
    amt = Decimal(rng.choice(["25.00", "50.00", "50.00", "100.00"]))
    header = [store, d.isoformat(), check_no, opened.strftime("%H:%M:%S"),
              (opened + timedelta(seconds=rng.randint(20, 90))).strftime("%H:%M:%S"), "GIFT", 1,
              amt, Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), amt,
              rng.choice(["CASH", "DEBIT", "VISA"]), "N", "", rng.choice(emp_ids)]
    return header, [[MICROS_GIFT_LOAD[0], MICROS_GIFT_LOAD[1], 1, amt, amt, "GIFT"]]


for store_row in micros_stores:
    store = store_row[0]
    factor = store_row[8]
    emp_ids = [f"{store}{n:02d}" for n in rng.sample(range(1, 40), 5)]
    check_no = rng.randint(50000, 59000)
    for d in business_dates():
        ds = d.isoformat()
        day_h, day_d = [], []
        sale_checks = []                 # (header, lines, channel)
        n = round(BASE_CHECKS[d.weekday()] * factor * rng.uniform(0.9, 1.1))
        n_gift = rng.choices([0, 1, 2, 3], weights=[25, 40, 25, 10])[0]
        kinds = ["SALE"] * n + ["GIFT"] * n_gift
        rng.shuffle(kinds)
        produced = []
        for kind in kinds:
            if kind == "SALE":
                h, lines, ch = make_sale_check(store, d, 0, emp_ids)
                sale_checks.append((h, lines, ch))
            else:
                h, lines = make_gift_load(store, d, 0, emp_ids)
            produced.append((h, lines))
        produced.sort(key=lambda x: x[0][3])          # check numbers follow open time
        for h, _ in produced:
            check_no += 1
            h[2] = check_no
            if h[5] == "GIFT":
                defects.append(["GIFT_CARD_LOAD_AS_SALE", store, ds, check_no, h[7],
                                "Gift card load rung up as a sale (order_type GIFT); not revenue, not royalty-bearing"])

        # Void posted after close: a reversing row for an earlier, completed in-store check
        voided = None
        if rng.random() < 0.45:
            candidates = [c for c in sale_checks if c[2] != "ONLINE"]
            voided = rng.choice(candidates)
            vh, vlines, _ = voided
            rev = list(vh)
            rev[4] = f"23:{rng.randint(50, 59)}:{rng.randrange(60):02d}"
            for i in (7, 8, 9, 10, 11):
                rev[i] = -vh[i]
            rev[13] = "V"
            rev_lines = [[l[0], l[1], -l[2], l[3], -l[4], "VOID"] for l in vlines]
            produced.append((rev, rev_lines))
            defects.append(["VOID_AFTER_CLOSE", store, ds, vh[2], -vh[7],
                            "Whole check voided by a reversing row posted after close (void_flag V, close_time 23:5x)"])

        for h, lines in produced:
            day_h.append(h)
            for i, l in enumerate(lines, 1):
                day_d.append([h[0], h[1], h[2], i] + l)

        # Duplicate polling: the last N checks are sent again at the end of the file
        dup_count = 0
        if (store, ds) == DUPLICATE_POLL[:2]:
            dup_count = DUPLICATE_POLL[2]
            dup_checks = [h for h in day_h if h[13] == "N"][-dup_count:]
            dup_nos = {h[2] for h in dup_checks}
            day_h.extend(list(h) for h in dup_checks)
            day_d.extend([list(r) for r in day_d if r[2] in dup_nos and r[9] != "VOID"])
            for h in dup_checks:
                defects.append(["DUPLICATE_POLL", store, ds, h[2], h[7],
                                "Check re-sent at the end of the day's file (exact duplicate header and detail rows)"])

        headers.setdefault(ds, []).extend(day_h)
        details.setdefault(ds, []).extend(day_d)

        for h, lines, ch in sale_checks:
            if ch == "ONLINE":
                online_refs.append([store, ds, h[2], h[14], h[5], h[7], h[8], h[9], h[10], h[11]])

        # True figures for this store-day (what a correct pipeline should report)
        real = [c for c in sale_checks if c is not voided]
        true_rows.append([
            store, ds, len(real),
            sum((c[0][7] for c in real), Decimal("0")),
            sum((c[0][8] for c in real), Decimal("0")),
            sum((c[0][7] - c[0][8] for c in real), Decimal("0")),
            sum((c[0][9] for c in real), Decimal("0")),
            sum((c[0][7] - c[0][8] for c in real if c[2] == "ONLINE"), Decimal("0")),
        ])

# Online order IDs come from the app, so renumber them in the order the orders were placed
all_online = sorted({(h[1], h[3], h[0], h[14]) for rows in headers.values() for h in rows if h[14]})
remap, seq = {}, 884000
for _, _, _, ref in all_online:
    if ref not in remap:
        seq += rng.randint(1, 9)
        remap[ref] = f"{ref[:5]}{seq}"
for rows in headers.values():
    for h in rows:
        if h[14]:
            h[14] = remap[h[14]]
for r in online_refs:
    r[3] = remap[r[3]]
online_refs.sort(key=lambda r: r[3][5:])

os.makedirs(os.path.join(OUT, P["micros"]), exist_ok=True)
key_dir = os.path.join(OUT, P["answer_key"])
os.makedirs(key_dir, exist_ok=True)


def fmt(v):
    return f"{v:.2f}" if isinstance(v, Decimal) else ("" if v is None else str(v))


def write_pipe(path, cols, rows):
    with open(path, "w", newline="") as f:
        f.write("|".join(cols) + "\r\n")
        for r in rows:
            f.write("|".join(fmt(v) for v in r) + "\r\n")


for ds in sorted(headers):
    tag = ds.replace("-", "")
    write_pipe(os.path.join(OUT, P["micros"], f"check_header_{tag}.txt"), HEADER_COLS, headers[ds])
    write_pipe(os.path.join(OUT, P["micros"], f"check_detail_{tag}.txt"), DETAIL_COLS, details[ds])

# Raw control totals: exactly what is in the files, so a Bronze load can be checked row for row
with open(os.path.join(key_dir, "micros_control_totals.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store", "business_date", "header_rows", "detail_rows", "sum_subtotal", "sum_discount",
                "sum_tax", "sum_tip", "sum_total"])
    for ds in sorted(headers):
        for store in sorted({h[0] for h in headers[ds]}):
            hs = [h for h in headers[ds] if h[0] == store]
            dl = [r for r in details[ds] if r[0] == store]
            w.writerow([store, ds, len(hs), len(dl)] + [fmt(sum((h[i] for h in hs), Decimal("0"))) for i in (7, 8, 9, 10, 11)])

with open(os.path.join(key_dir, "micros_true_net_sales.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store", "business_date", "sale_checks", "gross_sales", "discounts", "net_sales",
                "tax", "net_sales_from_online_orders"])
    w.writerows([[fmt(v) for v in r] for r in true_rows])

with open(os.path.join(key_dir, "micros_planted_defects.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["defect_type", "store", "business_date", "check_no", "amount", "description"])
    w.writerows([[fmt(v) for v in r] for r in defects])

with open(os.path.join(key_dir, "micros_online_refs.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store", "business_date", "check_no", "online_ref", "order_type", "subtotal",
                "discount", "tax", "tip", "total"])
    w.writerows([[fmt(v) for v in r] for r in online_refs])

print(f"MICROS: {sum(len(v) for v in headers.values())} header rows, "
      f"{sum(len(v) for v in details.values())} detail rows, {len(defects)} defect records")
