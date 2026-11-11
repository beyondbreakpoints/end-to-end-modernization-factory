"""Generates the IBM i (AS/400) commissary extracts: item master, shipments and store stock counts,
all fixed-width with COBOL copybooks, plus head office recipes and answer-key files.

Run after generate_micros.py and generate_aloha.py: theoretical usage comes from what the tills sold.

Output (under <out>/):
  commissary/ITEMMAST.TXT, SHP<CYYMMDD>.TXT, CNT<CYYMMDD>.TXT, *.CPY
  master/recipes.csv
  answer_key/commissary_*.csv
"""
import csv, glob, math, os, random, sys
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from common import P, SEED, STORES, MENU, business_dates, money

OUT = sys.argv[1] if len(sys.argv) > 1 else ".."
rng = random.Random(SEED + 4)
D = Decimal

# code, description (max 20), base unit, base units per case, case cost
ITEMS = [
    ("MOZ00410", "MOZZ SHRED 4X2.5KG",   "KG", "10.000", "84.50"),
    ("SAU00310", "PIZZA SAUCE 6X2.8KG",  "KG", "16.800", "38.40"),
    ("DGH00110", "DOUGH BALL SM 30CT",   "EA", "30.000", "27.00"),
    ("DGH00115", "DOUGH BALL MD 24CT",   "EA", "24.000", "26.40"),
    ("DGH00120", "DOUGH BALL LG 20CT",   "EA", "20.000", "31.25"),
    ("PEP00230", "PEPPERONI SLCD 2X2KG", "KG", "4.000",  "46.80"),
    ("HAM00240", "HAM DICED 2X2KG",      "KG", "4.000",  "42.00"),
    ("PIN00250", "PINEAPPLE TID 6X1.5K", "KG", "9.000",  "31.50"),
    ("VEG00260", "VEG MIX FRESH 4KG",    "KG", "4.000",  "22.80"),
    ("SAS00270", "SAUSAGE CRMBL 2X2KG",  "KG", "4.000",  "44.00"),
    ("BAC00280", "BACON BITS 2X1KG",     "KG", "2.000",  "36.00"),
    ("CHK00290", "CHICKEN GRLD 2X2KG",   "KG", "4.000",  "52.00"),
    ("BBQ00320", "BBQ SAUCE 4X2KG",      "KG", "8.000",  "28.00"),
    ("BAS00330", "BASIL FRESH 0.5KG",    "KG", "0.500",  "18.00"),
    ("WNG00510", "WINGS RAW 4X2KG",      "KG", "8.000",  "72.00"),
    ("GRB00520", "GARLIC LOAF 24CT",     "EA", "24.000", "30.00"),
    ("DIP00530", "GARLIC DIP 100X28G",   "EA", "100.000","22.00"),
    ("CIN00540", "CINN BITES 40CT",      "EA", "40.000", "34.00"),
    ("CAE00550", "CAESAR KIT 12CT",      "EA", "12.000", "36.00"),
]
ITEM = {i[0]: i for i in ITEMS}
CHEESE = "MOZ00410"
CHEESE_KG_PRICE = D("8.45")          # price per kg when the acquired stores order cheese by weight
SHRINK_STORES = {1055: D("0.16"), 2214: D("0.14")}   # cheese "going missing": extra actual usage
DOUGH = {"S": "DGH00110", "M": "DGH00115", "L": "DGH00120"}
CHEESE_KG = {"S": "0.140", "M": "0.200", "L": "0.280"}
SAUCE_KG = {"S": "0.080", "M": "0.110", "L": "0.150"}
TOPPINGS = {   # pizza type -> [(item, kg for a large)]; small = 50%, medium = 72% of large
    "PEP": [("PEP00230", "0.090")],
    "MAR": [("BAS00330", "0.008")],
    "HAW": [("HAM00240", "0.080"), ("PIN00250", "0.090")],
    "VEG": [("VEG00260", "0.180")],
    "MTL": [("PEP00230", "0.060"), ("SAS00270", "0.070"), ("BAC00280", "0.040"), ("HAM00240", "0.040")],
    "BBQ": [("CHK00290", "0.110")],
}
SIZE_FACTOR = {"S": D("0.50"), "M": D("0.72"), "L": D("1")}
SIDES = {"SD-GARLIC": [("GRB00520", "1"), (CHEESE, "0.030")], "SD-WING10": [("WNG00510", "0.550")],
         "SD-DIP": [("DIP00530", "1")], "DS-CINN": [("CIN00540", "1")], "SD-CAESAR": [("CAE00550", "1")]}


def recipe(m):
    sku, cat, size = m[0], m[2], m[3]
    if cat == "PIZZA":
        kind = sku.split("-")[1]
        r = [(DOUGH[size], D("1")), (CHEESE, D(CHEESE_KG[size]) * (D("1.2") if kind == "MAR" else 1))]
        r.append(("BBQ00320" if kind == "BBQ" else "SAU00310", D(SAUCE_KG[size])))
        r += [(i, (D(q) * SIZE_FACTOR[size]).quantize(D("0.001"))) for i, q in TOPPINGS[kind]]
        return r
    return [(i, D(q)) for i, q in SIDES.get(sku, [])]


RECIPES = {m[0]: recipe(m) for m in MENU}
SKU_BY_MICROS = {str(m[5]): m[0] for m in MENU}
SKU_BY_ALOHA = {m[7]: m[0] for m in MENU}

# ------------------------------------------------------------------ what the tills actually sold
sold = defaultdict(lambda: defaultdict(D))      # (store, date) -> sku -> qty
for f in sorted(glob.glob(os.path.join(OUT, P["micros"], "check_header_*.txt"))):
    with open(f, newline="") as fh:
        voided = {(h["store"], h["check_no"]) for h in csv.DictReader(fh, delimiter="|") if h["void_flag"] == "V"}
    with open(f.replace("check_header", "check_detail"), newline="") as fh:
        seen = set()
        for r in csv.DictReader(fh, delimiter="|"):
            k = (r["store"], r["check_no"], r["line_no"])
            if r["line_type"] != "ITEM" or k in seen or (r["store"], r["check_no"]) in voided:
                continue
            seen.add(k)
            sold[(int(r["store"]), r["business_date"])][SKU_BY_MICROS[r["item_no"]]] += D(r["qty"])
for f in sorted(glob.glob(os.path.join(OUT, P["aloha"], "*", "*", "ITEMS.csv"))):
    with open(f, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["TYPE"] == "ITEM":
                dob = f"{r['DOB'][:4]}-{r['DOB'][4:6]}-{r['DOB'][6:]}"
                sold[(int(r["STORE"]), dob)][SKU_BY_ALOHA[r["ITEMCODE"]]] += D(r["QTY"])

theo = defaultdict(lambda: defaultdict(D))      # (store, date) -> item -> base units
for key, skus in sold.items():
    for sku, q in skus.items():
        for item, per in RECIPES[sku]:
            theo[key][item] += per * q


def cyymmdd(d):
    return f"{(d.year - 1900) // 100}{d.strftime('%y%m%d')}"


def fixed_num(v, digits, decimals):
    return f"{int((abs(v) * 10 ** decimals).quantize(D('1'))):0{digits}d}"


dates = business_dates()
ship_days = [d for d in dates if d.weekday() in (0, 2, 4)]
ship_lines = defaultdict(list)                  # date -> fixed-width lines
counts = {"O": [], "C": []}
usage_rows, defects = [], []

for s in STORES:
    store, is_aloha = s[0], s[6] == "ALOHA"
    for code, desc, base, per_case, case_cost in ITEMS:
        per_case, case_cost = D(per_case), D(case_cost)
        waste = D(str(round(rng.uniform(0.015, 0.045), 3)))
        extra = SHRINK_STORES.get(store, D("0")) if code == CHEESE else D("0")
        daily_theo = [theo[(store, d.isoformat())][code] for d in dates]
        daily_actual = [(t * (1 + waste + extra)).quantize(D("0.001")) for t in daily_theo]
        avg = sum(daily_actual) / len(dates)
        if avg == 0:
            continue
        opening = (avg * D(str(round(rng.uniform(1.2, 2.2), 2))))
        opening = opening.quantize(D("1")) if base == "EA" else opening.quantize(D("0.1"))
        inv, received = opening, D("0")
        for i, d in enumerate(dates):
            if d in ship_days:
                days_cover = D("3.5") if d.weekday() == 4 else D("2.5")
                need = avg * days_cover * D("1.15") - inv
                if need > 0:
                    if code == CHEESE and is_aloha:          # acquired stores order cheese by the kilogram
                        qty = D(math.ceil(need / D("2.5"))) * D("2.5")
                        cost = money(qty * CHEESE_KG_PRICE)
                        uom, base_qty = "KG", qty
                        defects.append(["CHEESE_SHIPPED_IN_KG", store, d.isoformat(), code, f"{qty:.2f}",
                                        "Quantity is kilograms, not cases; dividing by 10 kg per case gives cases"])
                    else:
                        qty = D(math.ceil(need / per_case))
                        cost = money(qty * case_cost)
                        uom, base_qty = "CS", qty * per_case
                    ship_lines[d].append((store, d, code, desc, qty, uom, cost))
                    inv += base_qty
                    received += base_qty
            inv -= daily_actual[i]
        if inv < 0:                                   # never let a store run out on paper
            fix = D(math.ceil(-inv / per_case)) + 1
            ship_lines[dates[-1]].append((store, dates[-1], code, desc, fix, "CS", money(fix * case_cost)))
            inv += fix * per_case
            received += fix * per_case
        closing = inv.quantize(D("1")) if base == "EA" else inv.quantize(D("0.1"))
        counts["O"].append((store, dates[0], code, opening, base))
        counts["C"].append((store, dates[-1], code, closing, base))
        unit_cost = case_cost / per_case
        theo_total = sum(daily_theo)
        actual_total = opening + received - closing
        usage_rows.append([store, code, desc.strip(), base, opening, received, closing, actual_total,
                           theo_total.quantize(D("0.001")), (actual_total - theo_total).quantize(D("0.001")),
                           f"{(actual_total - theo_total) / theo_total * 100:.1f}" if theo_total else "",
                           money((actual_total - theo_total) * unit_cost)])

# A few credits: a damaged case sent back. The quantity is unsigned; only the cost carries the minus sign
# The case leaves the store, so received and the closing count both drop by one case; usage is unchanged
credits = 0
while credits < 3:
    d = rng.choice(ship_days)
    store, _, code, desc, qty, uom, cost = rng.choice([l for l in ship_lines[d] if l[5] == "CS"])
    per_case = D(ITEM[code][3])
    row = next(r for r in usage_rows if r[0] == store and r[1] == code)
    if row[6] < per_case:
        continue
    credits += 1
    ship_lines[d].append((store, d, code, desc, D("1"), "CS", -D(ITEM[code][4])))
    defects.append(["CREDIT_LINE", store, d.isoformat(), code, "1.00",
                    "Damaged case returned: quantity is unsigned, only the trailing minus on the cost marks a credit"])
    row[5] -= per_case                           # received
    row[6] -= per_case                           # closing count
    for i, c in enumerate(counts["C"]):
        if c[0] == store and c[2] == code:
            counts["C"][i] = (c[0], c[1], c[2], c[3] - per_case, c[4])

for store, pct in SHRINK_STORES.items():
    defects.append(["CHEESE_SHRINK", store, "", CHEESE, "",
                    f"Cheese used is about {pct * 100:.0f}% above recipe plus normal waste; the variance the business wants to find"])

# ------------------------------------------------------------------ write fixed-width files
cdir = os.path.join(OUT, P["commissary"])
os.makedirs(cdir, exist_ok=True)


def write_lines(name, lines):
    with open(os.path.join(cdir, name), "w", newline="") as f:
        for l in lines:
            f.write(l + "\r\n")


write_lines("ITEMMAST.TXT", [f"{c:<8}{d:<20}CS{b:<2}{fixed_num(D(p), 7, 3)}{fixed_num(D(k), 7, 2)}A"
                             for c, d, b, p, k in ITEMS])
control = []
for d in dates:
    lines = []
    for store, sd, code, desc, qty, uom, cost in sorted(ship_lines.get(d, []), key=lambda l: (l[0], l[2])):
        lines.append(f"{store:05d}{cyymmdd(sd)}{code:<8}{desc:<20}{fixed_num(qty, 7, 2)}{uom}"
                     f"{fixed_num(cost, 9, 2)}{'-' if cost < 0 else '+'}")
        assert len(lines[-1]) == 59
    if lines:
        write_lines(f"SHP{cyymmdd(d)}.TXT", lines)
        rows = ship_lines[d]
        control.append([f"SHP{cyymmdd(d)}.TXT", len(lines), f"{sum(l[4] for l in rows):.2f}",
                        f"{sum(l[6] for l in rows):.2f}"])
for kind, rows in counts.items():
    d = rows[0][1]
    write_lines(f"CNT{cyymmdd(d)}.TXT",
                [f"{st:05d}{cyymmdd(cd)}{kind}{code:<8}{fixed_num(q, 8, 3)}{b}" for st, cd, code, q, b in rows])
    control.append([f"CNT{cyymmdd(d)}.TXT", len(rows), f"{sum(r[3] for r in rows):.3f}", ""])

COPYBOOKS = {
    "ITEMREC.CPY": """      * ITEM MASTER  -  FILE ITEMMAST  -  RECORD LENGTH 47
       01  ITEM-REC.
           05  IT-ITEM-CODE      PIC X(8).
           05  IT-ITEM-DESC      PIC X(20).
           05  IT-PACK-UOM       PIC X(2).
      *        CS = CASE
           05  IT-BASE-UOM       PIC X(2).
      *        KG = KILOGRAM, EA = EACH
           05  IT-PACK-QTY       PIC 9(4)V999.
      *        BASE UNITS PER CASE, 3 IMPLIED DECIMALS
           05  IT-PACK-COST      PIC 9(5)V99.
      *        COST PER CASE IN CAD, 2 IMPLIED DECIMALS
           05  IT-STATUS         PIC X(1).
      *        A = ACTIVE
""",
    "SHIPREC.CPY": """      * SHIPMENT HISTORY  -  FILES SHPCYYMMDD  -  RECORD LENGTH 59
       01  SHIP-REC.
           05  SH-STORE-NO       PIC 9(5).
           05  SH-SHIP-DATE      PIC 9(7).
      *        CYYMMDD  C=1 FOR 20XX  1260309 = 2026-03-09
           05  SH-ITEM-CODE      PIC X(8).
           05  SH-ITEM-DESC      PIC X(20).
           05  SH-QTY            PIC 9(5)V99.
      *        2 IMPLIED DECIMALS  0000600 = 6.00
           05  SH-UOM            PIC X(2).
      *        CS = CASE, KG = KILOGRAM
           05  SH-EXT-COST       PIC S9(7)V99 SIGN TRAILING SEPARATE.
      *        EXTENDED COST IN CAD  -  TRAILING - MARKS A CREDIT
""",
    "CNTREC.CPY": """      * STORE STOCK COUNT  -  FILES CNTCYYMMDD  -  RECORD LENGTH 31
       01  COUNT-REC.
           05  CT-STORE-NO       PIC 9(5).
           05  CT-COUNT-DATE     PIC 9(7).
      *        CYYMMDD
           05  CT-COUNT-TYPE     PIC X(1).
      *        O = OPENING COUNT (BEFORE TRADING), C = CLOSING COUNT (AFTER TRADING)
           05  CT-ITEM-CODE      PIC X(8).
           05  CT-QTY-ON-HAND    PIC 9(5)V999.
      *        IN BASE UNITS, 3 IMPLIED DECIMALS
           05  CT-BASE-UOM       PIC X(2).
""",
}
for name, text in COPYBOOKS.items():
    with open(os.path.join(cdir, name), "w", newline="") as f:
        f.write(text.replace("\n", "\r\n"))

with open(os.path.join(OUT, P["master"], "recipes.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["sku", "ingredient_item_code", "qty_per_unit", "base_uom"])
    for m in MENU:
        for item, q in RECIPES[m[0]]:
            w.writerow([m[0], item, f"{q:.3f}", ITEM[item][2]])

key = os.path.join(OUT, P["answer_key"])
with open(os.path.join(key, "commissary_true_usage.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store", "item_code", "item_desc", "base_uom", "opening_count", "received", "closing_count",
                "actual_usage", "theoretical_usage", "variance", "variance_pct", "variance_cost"])
    w.writerows([[f"{v}" if not isinstance(v, D) else (f"{v:.3f}" if i < 11 else f"{v:.2f}")
                  for i, v in enumerate(r)] for r in usage_rows])
with open(os.path.join(key, "commissary_planted_defects.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["defect_type", "store", "ship_date", "item_code", "qty", "description"])
    w.writerows(defects)
with open(os.path.join(key, "commissary_control_totals.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["file", "records", "sum_qty", "sum_ext_cost"])
    w.writerows(control)

print(f"Commissary: {sum(len(v) for v in ship_lines.values())} shipment lines in {len(ship_days)} files, "
      f"{len(counts['O']) + len(counts['C'])} count records, {len(defects)} defect records")
