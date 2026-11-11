"""Writes the shared master data every source system is generated from: stores, menu, calendar."""
import csv, os, sys
from decimal import Decimal
from common import P, STORES, MENU, HST, business_dates, money

OUT = sys.argv[1] if len(sys.argv) > 1 else ".."
out = os.path.join(OUT, P["master"])
os.makedirs(out, exist_ok=True)

with open(os.path.join(out, "stores.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["store_id", "store_name", "city", "province", "ownership", "franchisee_id",
                "franchisee_name", "pos_system", "open_date"])
    for s in STORES:
        w.writerow([s[0], s[1], s[2], "ON", s[3], s[4], s[5], s[6], s[7]])

# HQ menu master: knows its own SKUs and the original MICROS item numbers, but not the Aloha codes
with open(os.path.join(out, "menu.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["sku", "item_name", "category", "size", "price_excl_tax", "micros_item_no"])
    for m in MENU:
        w.writerow([m[0], m[1], m[2], m[3], m[4], m[5]])

# Full crosswalk, including Aloha codes: answer key only, never loaded as a source
key = os.path.join(OUT, P["answer_key"])
os.makedirs(key, exist_ok=True)
with open(os.path.join(key, "menu_crosswalk.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["sku", "item_name", "price_excl_tax", "price_incl_tax",
                "micros_item_no", "micros_item_name", "aloha_item_code", "aloha_item_name"])
    for m in MENU:
        p = Decimal(m[4])
        w.writerow([m[0], m[1], m[4], money(p * (1 + HST)), m[5], m[6], m[7], m[8]])

with open(os.path.join(out, "calendar.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["business_date", "day_name", "is_2for1_tuesday"])
    for d in business_dates():
        w.writerow([d.isoformat(), d.strftime("%A"), "Y" if d.weekday() == 1 else "N"])
print("master data written to", out)
