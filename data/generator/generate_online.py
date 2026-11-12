"""Generates the custom online ordering and loyalty app's exports (MySQL app built in 2015).

Run after generate_micros.py and generate_aloha.py: every completed app order is the same sale as a
till check, so the app is built from the tills' online orders.

Output (under <out>/):
  online/orders_YYYYMMDD.json   orders by the calendar date they were placed (local time)
  online/customers.csv          loyalty accounts, including duplicate accounts for the same person
  answer_key/online_*.csv
"""
import csv, glob, json, os, random, sys
from datetime import datetime, timedelta, date
from decimal import Decimal
from common import P, SEED, STORES, MENU, HST, business_dates, money

OUT = sys.argv[1] if len(sys.argv) > 1 else ".."
rng = random.Random(SEED + 3)
TZ = "-04:00"   # Ontario is on daylight time from 8 March 2026

MENU_BY_SKU = {m[0]: m for m in MENU}
SKU_BY_MICROS = {str(m[5]): m[0] for m in MENU}
STORE_CITY = {s[0]: s[2] for s in STORES}
AREA_CODES = {"Toronto": ["416", "647", "437"], "Mississauga": ["905", "289"], "Brampton": ["905", "365"],
              "Oakville": ["289", "905"], "Hamilton": ["905", "365"], "Ottawa": ["613", "343"],
              "Kingston": ["613", "343"], "Barrie": ["705", "249"]}
FIRST = ["Priya", "Marc", "Dana", "Liam", "Olivia", "Noah", "Emma", "Arjun", "Mei", "Lucas", "Sofia", "Ethan",
         "Aisha", "Daniel", "Chloe", "Omar", "Hannah", "Wei", "Isabelle", "Jamal", "Grace", "Mateo", "Fatima",
         "Ryan", "Zoe", "Kenji", "Leah", "Hassan", "Nadia", "Owen", "Amara", "Julien", "Simran", "Tyler",
         "Maya", "Diego", "Ananya", "Connor", "Yasmin", "Gabriel", "Rosa", "Kofi", "Elena", "Sam", "Tara"]
LAST = ["Raman", "Tremblay", "Okafor", "Smith", "Nguyen", "Patel", "Chen", "Gagnon", "Singh", "Martin",
        "Wilson", "Kim", "Ahmed", "Roy", "Brown", "Haddad", "Li", "Campbell", "Fernandes", "MacDonald",
        "Osei", "Kowalski", "Bouchard", "Sharma", "Taylor", "Ali", "Lefebvre", "Wong", "Murphy", "Rossi",
        "Mensah", "Côté", "Gill", "Anderson", "Park", "Dubois", "Khan", "Reid", "Silva", "Hughes"]
DOMAINS = ["example.com", "example.net", "example.org"]


def fmt(v):
    return f"{v:.2f}" if isinstance(v, Decimal) else ("" if v is None else str(v))


# ---------------------------------------------------------------- read the tills' online orders
orders = []   # dicts in a common shape
for f in sorted(glob.glob(os.path.join(OUT, P["micros"], "check_header_*.txt"))):
    with open(f, newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="|"))
    seen = set()
    for h in rows:
        key = (h["store"], h["check_no"])
        if not h["online_ref"] or h["void_flag"] != "N" or key in seen:
            continue
        seen.add(key)
        orders.append({"src": "MICROS", "store": int(h["store"]), "business_date": h["business_date"],
                       "check_no": int(h["check_no"]), "ref": h["online_ref"],
                       "placed": datetime.fromisoformat(f'{h["business_date"]}T{h["open_time"]}') - timedelta(minutes=2),
                       "mode": "delivery" if h["order_type"] == "DELIV" else "pickup",
                       "subtotal": Decimal(h["subtotal"]), "discount": Decimal(h["discount"]),
                       "tax": Decimal(h["tax"]), "tip": Decimal(h["tip"]), "items": [], "promo": None})
by_check = {(o["store"], o["business_date"], o["check_no"]): o for o in orders}
for f in sorted(glob.glob(os.path.join(OUT, P["micros"], "check_detail_*.txt"))):
    with open(f, newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="|"))
    done = set()
    for r in rows:
        o = by_check.get((int(r["store"]), r["business_date"], int(r["check_no"])))
        if not o or r["line_type"] not in ("ITEM", "DISC"):
            continue
        k = (r["store"], r["check_no"], r["line_no"])
        if k in done:       # duplicated polling rows
            continue
        done.add(k)
        if r["line_type"] == "ITEM":
            o["items"].append((SKU_BY_MICROS[r["item_no"]], int(r["qty"])))
        else:
            o["promo"] = {"9001": "2FOR1TUE", "9002": "WELCOME10", "9003": None}[r["item_no"]]

with open(os.path.join(OUT, P["answer_key"], "aloha_online_orders.csv"), newline="") as fh:
    for r in csv.DictReader(fh):
        items = [(p.split("x")[0], int(p.split("x")[1])) for p in r["items"].split(";")]
        subtotal = sum((Decimal(MENU_BY_SKU[s][4]) * q for s, q in items), Decimal("0"))
        discount = Decimal("0")
        promo = None
        if date.fromisoformat(r["business_date"]).weekday() == 1:
            larges = sorted(Decimal(MENU_BY_SKU[s][4]) for s, q in items if MENU_BY_SKU[s][3] == "L" for _ in range(q))
            discount = sum(larges[: len(larges) // 2], Decimal("0"))
            promo = "2FOR1TUE" if discount else None
        orders.append({"src": "ALOHA", "store": int(r["store"]), "business_date": r["business_date"],
                       "check_no": int(r["check_id"]), "ref": None,
                       "placed": datetime.fromisoformat(r["placed_at"]) - timedelta(minutes=2),
                       "mode": "delivery" if r["order_mode"] == "DELIVERY" else "pickup",
                       "subtotal": subtotal, "discount": discount,
                       "tax": money((subtotal - discount) * HST), "tip": Decimal(r["tip"]),
                       "items": items, "promo": promo})

# Cancelled orders: placed in the app, never sent to a till
cancelled = []
for d in business_dates():
    for store in [s[0] for s in STORES]:
        for _ in range(rng.choices([0, 1, 2], weights=[45, 40, 15])[0]):
            items = [(rng.choice(MENU)[0], 1) for _ in range(rng.randint(1, 3))]
            subtotal = sum((Decimal(MENU_BY_SKU[s][4]) * q for s, q in items), Decimal("0"))
            cancelled.append({"src": None, "store": store, "business_date": d.isoformat(), "check_no": None,
                              "ref": None, "placed": datetime(d.year, d.month, d.day, rng.randint(11, 21), rng.randrange(60), rng.randrange(60)),
                              "mode": rng.choice(["delivery", "pickup"]), "subtotal": subtotal,
                              "discount": Decimal("0"), "tax": money(subtotal * HST), "tip": Decimal("0"),
                              "items": items, "promo": None, "cancelled": True})
orders += cancelled

# ---------------------------------------------------------------- order IDs (MICROS ones are fixed)
used = {int(o["ref"][5:]) for o in orders if o["ref"]}
last = 884000
for o in sorted(orders, key=lambda o: o["placed"]):
    if o["ref"]:
        last = max(last, int(o["ref"][5:]))
        continue
    n = last + 1
    while n in used:
        n += 1
    used.add(n)
    last = n
    o["ref"] = f"PS-{rng.choice(['W', 'A'])}-{n}"

# ---------------------------------------------------------------- customers, with duplicate accounts
people, accounts, phones = [], [], set()
cust_id = 18000


ALL_AREAS = ["416", "647", "437", "905", "289", "365", "613", "343", "705", "249", "519", "226", "548", "807"]


def new_phone(city):
    """Fictional 555-01xx numbers, unique per person; falls back to other Ontario area codes when a city's run out."""
    for areas in (AREA_CODES[city], ALL_AREAS):
        free = [(a, f"{n:04d}") for a in areas for n in range(100, 200) if (a, f"{n:04d}") not in phones]
        if free:
            p = rng.choice(free)
            phones.add(p)
            return p
    raise RuntimeError("ran out of fictional phone numbers")


def add_account(person, variant):
    global cust_id
    cust_id += rng.randint(1, 25)
    first, last_ = person["first"], person["last"]
    area, line = person["phone"]
    if variant == 0:
        name = f"{first} {last_}"
        email = f"{first.lower()}.{last_.lower().replace('ô', 'o').replace('é', 'e')}@{person['domain']}"
        phone = f"{area}-555-{line}"
    else:   # a second account made later, by the same person
        name = rng.choice([f"{first} {last_}".upper(), f"{first[0]}. {last_}", f"{first} {last_}"])
        email = f"{first[0].lower()}{last_.lower().replace('ô', 'o').replace('é', 'e')}{rng.randint(1, 99)}@{rng.choice(DOMAINS)}"
        phone = rng.choice([f"+1{area}555{line}", f"({area}) 555-{line}", f"{area}555{line}"])
    created = datetime(2023, 1, 1) + timedelta(days=rng.randint(0, 1150), seconds=rng.randint(0, 86399))
    acc = {"customer_id": cust_id, "name": name, "email": email, "phone": phone, "created_at": created,
           "person_id": person["person_id"], "home_store": person["home_store"], "points": 0}
    accounts.append(acc)
    return acc


for store in [s[0] for s in STORES]:
    n_people = {s[0]: round(140 * s[8]) for s in STORES}[store]
    for _ in range(n_people):
        person = {"person_id": f"P{len(people) + 1:05d}", "first": rng.choice(FIRST), "last": rng.choice(LAST),
                  "domain": rng.choice(DOMAINS), "home_store": store, "phone": new_phone(STORE_CITY[store])}
        person["accounts"] = [add_account(person, 0)]
        if rng.random() < 0.10:
            person["accounts"].append(add_account(person, 1))
        person["weight"] = rng.choice([1, 1, 1, 2, 3, 6])
        people.append(person)

by_store = {}
for p in people:
    by_store.setdefault(p["home_store"], []).append(p)
for o in orders:
    pool = by_store[o["store"]]
    p = rng.choices(pool, weights=[x["weight"] for x in pool])[0]
    acc = rng.choice(p["accounts"])
    o["account"] = acc
    if not o.get("cancelled"):
        acc["points"] += int(o["subtotal"] - o["discount"])

# Every account has to exist before it places its first order
first_order = {}
for o in orders:
    a = o["account"]["customer_id"]
    first_order[a] = min(first_order.get(a, o["placed"]), o["placed"])
for a in accounts:
    if a["customer_id"] in first_order and a["created_at"] > first_order[a["customer_id"]]:
        a["created_at"] = first_order[a["customer_id"]] - timedelta(days=rng.randint(1, 400))

# ---------------------------------------------------------------- write the exports
os.makedirs(os.path.join(OUT, P["online"]), exist_ok=True)
by_day = {}
for o in sorted(orders, key=lambda o: o["placed"]):
    acc = o["account"]
    status = "cancelled" if o.get("cancelled") else "completed"
    rec = {
        "order_id": o["ref"],
        "placed_at": o["placed"].strftime("%Y-%m-%dT%H:%M:%S") + TZ,
        "store_id": o["store"],
        "channel": "web" if o["ref"][3] == "W" else "app",
        "fulfilment": o["mode"],
        "status": status,
        "promo_code": o["promo"],
        "customer": {"id": acc["customer_id"], "name": acc["name"], "email": acc["email"], "phone": acc["phone"]},
        "items": [{"sku": s, "name": MENU_BY_SKU[s][1], "qty": q, "unit_price": float(MENU_BY_SKU[s][4])}
                  for s, q in o["items"]],
        "subtotal": float(o["subtotal"]), "discount": float(o["discount"]), "tax": float(o["tax"]),
        "tip": float(o["tip"]), "total": float(o["subtotal"] - o["discount"] + o["tax"] + o["tip"]),
        "pos_check_no": o["check_no"] if o["src"] == "MICROS" else None,
    }
    by_day.setdefault(o["placed"].strftime("%Y%m%d"), []).append(rec)
for day, recs in by_day.items():
    with open(os.path.join(OUT, P["online"], f"orders_{day}.json"), "w") as f:
        json.dump(recs, f, indent=1, ensure_ascii=False)

with open(os.path.join(OUT, P["online"], "customers.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["customer_id", "full_name", "email", "phone", "created_at", "home_store_id", "loyalty_points",
                "marketing_opt_in"])
    for a in sorted(accounts, key=lambda a: a["customer_id"]):
        w.writerow([a["customer_id"], a["name"], a["email"], a["phone"], a["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    a["home_store"], a["points"], rng.choice(["1", "0"])])

# ---------------------------------------------------------------- answer key
key = os.path.join(OUT, P["answer_key"])
with open(os.path.join(key, "online_order_match.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["order_id", "status", "store", "pos_system", "business_date", "pos_check_no", "net_sales_in_app",
                "match_note"])
    for o in sorted(orders, key=lambda o: o["ref"][5:]):
        if o.get("cancelled"):
            w.writerow([o["ref"], "cancelled", o["store"], "", o["business_date"], "", fmt(o["subtotal"] - o["discount"]),
                        "Never reached a till; not a sale"])
        else:
            note = ("Linked in the data by pos_check_no" if o["src"] == "MICROS"
                    else "No link in the data; match on store, time and amount")
            w.writerow([o["ref"], "completed", o["store"], o["src"], o["business_date"], o["check_no"],
                        fmt(o["subtotal"] - o["discount"]), note])

with open(os.path.join(key, "online_customer_identity.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["customer_id", "person_id", "accounts_for_this_person"])
    counts = {}
    for a in accounts:
        counts[a["person_id"]] = counts.get(a["person_id"], 0) + 1
    for a in sorted(accounts, key=lambda a: a["customer_id"]):
        w.writerow([a["customer_id"], a["person_id"], counts[a["person_id"]]])

with open(os.path.join(key, "online_control_totals.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["file", "orders", "completed", "cancelled", "sum_subtotal", "sum_discount", "sum_tax", "sum_tip", "sum_total"])
    for day in sorted(by_day):
        recs = by_day[day]
        s = lambda k: sum((Decimal(str(r[k])) for r in recs), Decimal("0"))
        w.writerow([f"orders_{day}.json", len(recs), sum(r["status"] == "completed" for r in recs),
                    sum(r["status"] == "cancelled" for r in recs)] + [fmt(s(k)) for k in ("subtotal", "discount", "tax", "tip", "total")])

dupe_people = sum(1 for p in people if len(p["accounts"]) > 1)
print(f"Online: {len(orders)} orders ({len(cancelled)} cancelled) in {len(by_day)} files, "
      f"{len(accounts)} customer accounts for {len(people)} people ({dupe_people} with two accounts)")
