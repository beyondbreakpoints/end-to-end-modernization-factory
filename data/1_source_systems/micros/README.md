# MICROS tills

Oracle MICROS RES 3700, the tills in Polar Slice's 7 original stores (1042, 1043, 1055, 1061, 1078, 1090 and 3015).

Pipe-delimited (`|`) text with a header row and Windows line endings (CRLF). All MICROS stores are in one file per day: `check_header_YYYYMMDD.txt` and `check_detail_YYYYMMDD.txt`.

## check_header_YYYYMMDD.txt

One row per check (order).

| Column | Meaning |
|---|---|
| store | Store number |
| business_date | Trading day, YYYY-MM-DD |
| check_no | Check number, increasing through the day per store |
| open_time, close_time | When the check was opened and closed (HH:MM:SS) |
| order_type | DINE, TAKE (pickup), DELIV (delivery) or GIFT (gift card load) |
| guest_count | Diners at the table; 1 for non-dine-in |
| subtotal | Sum of item prices before discount and tax |
| discount | Discount amount, as a positive number |
| tax | 13% HST on (subtotal − discount) |
| tip | Tip, if any |
| total | subtotal − discount + tax + tip (the total **includes** the tip) |
| tender | VISA, MC, AMEX, DEBIT, CASH, GIFTCARD, or WEB (paid online) |
| void_flag | N for a normal check, V for a reversing row that cancels a whole check |
| online_ref | The online app's order ID (PS-W- web, PS-A- app) when the order came through the app; blank otherwise |
| employee_id | Staff member who rang it in |

## check_detail_YYYYMMDD.txt

One row per line on a check. Join to the header on `store`, `business_date` and `check_no`.

| Column | Meaning |
|---|---|
| line_no | Line number within the check |
| item_no, item_name | MICROS item number and short name (for example 1103, LG PEPPERONI) |
| qty | Quantity (negative on VOID lines) |
| unit_price | Price per unit, before tax |
| line_amount | qty × unit_price (negative for discounts and voids) |
| line_type | ITEM, DISC (discount), GIFT (gift card load) or VOID (reversal) |

Line amounts for a check add up to the header's subtotal − discount. Discount item numbers: 9001 = 2-for-1 Tuesday (the cheaper large pizza in each pair is free), 9002 = WELCOME10 (10% off an online order), 9003 = STAFF 50.

## Watch out for

| Problem | How to spot it | How many |
|---|---|---|
| Gift card loads rung up as sales | `order_type = GIFT`. Selling a gift card isn't revenue and carries no royalty | 49 |
| Voids posted after close | A second row with the same `check_no`, `void_flag = V`, negative amounts and a close time after 23:50. Both rows together net to zero | 14 |
| Checks sent twice | Store 1061 on 2026-03-12: its last 12 checks appear twice, with identical header and detail rows | 12 checks |
| Online orders | Rows with an `online_ref` are also in the online app's export. Count them once | 1,637 |
