# Master data (head office)

Head office's reference data. In the legacy setup these live in SliceDW's `cfg` tables; here they're plain CSV files.

**stores.csv**: one row per store.

| Column | Meaning |
|---|---|
| store_id | Store number, used by every other system |
| store_name, city, province | Where the store is |
| ownership | FRANCHISE or CORPORATE (corporate stores pay no royalty) |
| franchisee_id, franchisee_name | The owner. F001 and F006 own two stores each |
| pos_system | Which till the store uses: MICROS or ALOHA |
| open_date | When the store opened. This matters for royalty: new stores get a 6-month royalty holiday, and store 1078 opened on 2025-12-01 |

**menu.csv**: head office's menu.

| Column | Meaning |
|---|---|
| sku | Master product code (for example PZ-PEP-L) |
| item_name | Full name (for example Large Pepperoni 14in) |
| category, size | PIZZA, SIDE, DESSERT or DRINK; S, M or L for pizzas |
| price_excl_tax | List price before tax |
| micros_item_no | The matching MICROS item number |

Head office doesn't have the Aloha codes. Matching those to the menu is part of the challenge.

**calendar.csv**: the five business dates, the day name, and a flag for 2-for-1 Tuesday.

**recipes.csv**: how much of each commissary ingredient goes into one unit of each menu item.

| Column | Meaning |
|---|---|
| sku | Menu item |
| ingredient_item_code | Commissary item code (see `as400_commissary/`) |
| qty_per_unit | Amount used per item sold |
| base_uom | KG or EA |

For example, a large pepperoni uses 1 large dough ball, 0.280 kg of cheese, 0.150 kg of sauce and 0.090 kg of pepperoni. Theoretical usage = items sold × recipe.
