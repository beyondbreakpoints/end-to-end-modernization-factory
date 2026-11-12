# Aloha tills

NCR Aloha, the tills in the 3 stores Polar Slice acquired in 2022 (2207, 2214 and 2231).

Comma-separated, with a header row. One folder per store per business day: `aloha/<store>/<YYYYMMDD>/CHECKS.csv` and `ITEMS.csv`.

## How Aloha differs from MICROS

- **Prices include tax.** Every price and amount already contains the 13% HST. `TAXINCL` is the tax portion inside `NETTOTAL`.
- **The business day ends at 4 a.m.** `DOB` (date of business) is the trading day. Orders after midnight keep the previous day's DOB, even though their timestamps show the next calendar date.
- **Timestamps are US style:** `MM/DD/YYYY HH:MM`.
- **Check numbers restart every day** at 10001, so a check is identified by `STORE` + `DOB` + `CHECKID`.
- **Item codes are short Aloha codes** (for example LGPEP), which head office's menu doesn't know.

## CHECKS.csv

One row per check.

| Column | Meaning |
|---|---|
| STORE, DOB, CHECKID | Store, business day (YYYYMMDD) and check number |
| TABLENUM | Table number for dine-in; blank otherwise |
| ORDERMODE | DINE IN, TO GO or DELIVERY |
| OPENTIME, CLOSETIME | When the check was opened and closed |
| GROSS | Item total, tax included, before comps |
| COMP | Discounts ("comps"), positive, tax included |
| NETTOTAL | GROSS − COMP, tax included |
| TAXINCL | The tax contained in NETTOTAL |
| TIP | Tip, if any |
| TOTAL | NETTOTAL + TIP |
| PAYTYPE | VISA, MASTERCARD, AMEX, INTERAC, CASH, or WEB (paid online) |
| EMPLOYEE | Server ID |

## ITEMS.csv

One row per item or comp: `STORE`, `DOB`, `CHECKID`, `ENTRYID`, `ITEMCODE`, `ITEMNAME`, `QTY`, `PRICE` (tax included), `AMOUNT` (QTY × PRICE), `TYPE` and `ORDERTIME`. `TYPE` is ITEM or COMP; the comp codes are 2F1TUE (2-for-1 Tuesday) and EMP50 (staff discount). Amounts for a check add up to its NETTOTAL.

## Watch out for

| Problem | How to spot it | How many |
|---|---|---|
| Tax-inclusive amounts | Counting NETTOTAL as net sales overstates sales by 13%. Net sales = NETTOTAL − TAXINCL | All 2,505 checks |
| After-midnight orders | CLOSETIME on the next calendar date. The DOB is the correct business day | 131 |
| Online orders with no link to the app | PAYTYPE = WEB, but no online order ID. They also appear in the app's export and can only be matched by store, time and amount | 631 |
| Unknown item codes | Aloha codes must be matched to head office's menu (by name, size and price) | 19 codes |
