"""Shared settings and master data for the Polar Slice Pizza legacy data generator."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

SEED = 20260309
START_DATE = date(2026, 3, 9)   # Monday
NUM_DAYS = 5                    # Mon 9 Mar to Fri 13 Mar 2026; Tuesday 10 Mar is 2-for-1 Tuesday
HST = Decimal("0.13")           # all stores are in Ontario

def business_dates():
    return [START_DATE + timedelta(days=i) for i in range(NUM_DAYS)]

def money(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# store_id, name, city, ownership, franchisee_id, franchisee_name, pos_system, open_date, volume factor
STORES = [
    (1042, "Queen St West",  "Toronto",     "FRANCHISE", "F001", "Rana Holdings Inc.",       "MICROS", "2014-05-12", 1.25),
    (1043, "Danforth",       "Toronto",     "FRANCHISE", "F002", "Kostas Food Group Ltd.",   "MICROS", "2016-09-01", 1.00),
    (1055, "Square One",     "Mississauga", "FRANCHISE", "F001", "Rana Holdings Inc.",       "MICROS", "2017-03-20", 1.10),
    (1061, "James St North", "Hamilton",    "FRANCHISE", "F003", "Steeltown Slices Inc.",    "MICROS", "2018-11-05", 0.85),
    (1078, "Kerr Village",   "Oakville",    "FRANCHISE", "F004", "Lakeshore QSR Corp.",      "MICROS", "2025-12-01", 0.70),
    (1090, "Bramalea",       "Brampton",    "FRANCHISE", "F005", "Dhillon Family Foods Ltd.","MICROS", "2019-06-17", 0.95),
    (3015, "Yonge & Eglinton","Toronto",    "CORPORATE", "",     "",                         "MICROS", "2012-02-01", 1.15),
    (2207, "Bank St",        "Ottawa",      "FRANCHISE", "F006", "Rideau Pizza Partners",    "ALOHA",  "2015-08-10", 1.05),
    (2214, "Princess St",    "Kingston",    "FRANCHISE", "F006", "Rideau Pizza Partners",    "ALOHA",  "2018-04-23", 0.80),
    (2231, "Bayfield",       "Barrie",      "FRANCHISE", "F007", "Georgian Bay Eats Inc.",   "ALOHA",  "2020-10-02", 0.75),
]

# sku, master name, category, size, price excl. tax, MICROS item no, MICROS name, Aloha code, Aloha name, popularity weight
MENU = [
    ("PZ-PEP-S", "Small Pepperoni 10in",     "PIZZA", "S", "9.49",  1101, "SM PEPPERONI",  "SMPEP",  "SM PEP",   6),
    ("PZ-PEP-M", "Medium Pepperoni 12in",    "PIZZA", "M", "11.99", 1102, "MD PEPPERONI",  "MDPEP",  "MD PEP",   10),
    ("PZ-PEP-L", "Large Pepperoni 14in",     "PIZZA", "L", "13.99", 1103, "LG PEPPERONI",  "LGPEP",  "LG PEP",   14),
    ("PZ-MAR-M", "Medium Margherita 12in",   "PIZZA", "M", "11.49", 1112, "MD MARGHERITA", "MDMARG", "MD MARG",  5),
    ("PZ-MAR-L", "Large Margherita 14in",    "PIZZA", "L", "13.49", 1113, "LG MARGHERITA", "LGMARG", "LG MARG",  6),
    ("PZ-HAW-M", "Medium Hawaiian 12in",     "PIZZA", "M", "12.49", 1122, "MD HAWAIIAN",   "MDHAW",  "MD HAW",   4),
    ("PZ-HAW-L", "Large Hawaiian 14in",      "PIZZA", "L", "14.49", 1123, "LG HAWAIIAN",   "LGHAW",  "LG HAW",   5),
    ("PZ-VEG-M", "Medium Veggie 12in",       "PIZZA", "M", "12.99", 1132, "MD VEGGIE",     "MDVEG",  "MD VEG",   4),
    ("PZ-VEG-L", "Large Veggie 14in",        "PIZZA", "L", "14.99", 1133, "LG VEGGIE",     "LGVEG",  "LG VEG",   5),
    ("PZ-MTL-M", "Medium Meat Lovers 12in",  "PIZZA", "M", "13.99", 1142, "MD MEAT LOVER", "MDMEAT", "MD MEAT",  4),
    ("PZ-MTL-L", "Large Meat Lovers 14in",   "PIZZA", "L", "16.49", 1143, "LG MEAT LOVER", "LGMEAT", "LG MEAT",  7),
    ("PZ-BBQ-L", "Large BBQ Chicken 14in",   "PIZZA", "L", "15.99", 1153, "LG BBQ CHKN",   "LGBBQ",  "LG BBQ",   4),
    ("SD-GARLIC","Garlic Bread",             "SIDE",  "",  "5.99",  2001, "GARLIC BREAD",  "GARBRD", "GAR BRD",  9),
    ("SD-WING10","Chicken Wings 10pc",       "SIDE",  "",  "12.99", 2010, "WINGS 10PC",    "WING10", "WINGS 10", 6),
    ("SD-CAESAR","Caesar Salad",             "SIDE",  "",  "7.49",  2020, "CAESAR SALAD",  "CAESAR", "CAESAR",   3),
    ("SD-DIP",   "Garlic Dip",               "SIDE",  "",  "0.99",  2030, "GARLIC DIP",    "DIPGAR", "DIP GAR",  8),
    ("DS-CINN",  "Cinnamon Bites",           "DESSERT","", "5.49",  3001, "CINNAMON BITE", "CINN",   "CINN BTE", 3),
    ("BV-POP2L", "Pop 2L",                   "DRINK", "",  "3.99",  4001, "POP 2L",        "POP2L",  "POP 2L",   6),
    ("BV-POPCAN","Pop Can 355ml",            "DRINK", "",  "1.79",  4002, "POP CAN",       "POPCAN", "POP CAN",  7),
]

# Non-menu POS keys
MICROS_GIFT_LOAD = (8001, "GIFT CARD LOAD")
MICROS_DISC_2F1 = (9001, "2F1 TUES")
MICROS_DISC_WELCOME = (9002, "WELCOME10")
MICROS_DISC_STAFF = (9003, "STAFF 50")

# Where each part of the data pack lives, relative to the pack's root folder
P = {
    "master":      "1_source_systems/master_data",
    "micros":      "1_source_systems/micros",
    "aloha":       "1_source_systems/aloha",
    "online":      "1_source_systems/online_app",
    "commissary":  "1_source_systems/as400_commissary",
    "slicedw":     "2_legacy_warehouse_slicedw",
    "slicedw_sql": "2_legacy_warehouse_slicedw/sql",
    "ssis":        "2_legacy_warehouse_slicedw/ssis_packages",
    "answer_key":  "3_answer_key",
}
