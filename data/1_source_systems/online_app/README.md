# Online ordering and loyalty app

A custom app built in 2015 on MySQL. It records the order and the customer, then sends the order to the store's till, which rings it up.

**The tills are the system of record for sales.** Every completed app order is also a till check, so adding the app's sales to the tills' counts them twice. The app is the source for customers, channels and promo codes.

## orders_YYYYMMDD.json

One JSON array per calendar day, by when the order was placed (Ontario time, UTC−04:00). Because Aloha stores take orders until about 2 a.m., `orders_20260314.json` holds 6 orders placed after midnight on the 13 March business day.

| Field | Meaning |
|---|---|
| order_id | PS-W-… (web) or PS-A-… (app). Mostly increasing over time, but not strictly |
| placed_at | When the customer placed the order |
| store_id | Store that made the order |
| channel, fulfilment | web or app; delivery or pickup |
| status | completed, or cancelled (never sent to a till) |
| promo_code | 2FOR1TUE, WELCOME10 or null |
| customer | The account that placed the order: id, name, email and phone, as they were at the time |
| items | sku, name, qty and unit_price, **before tax**, using head office's SKUs and prices |
| subtotal, discount, tax, tip, total | Order amounts; total = subtotal − discount + tax + tip |
| pos_check_no | The MICROS check number for orders at MICROS stores; **null for Aloha stores**, whose integration never sent it back |

## customers.csv

One row per loyalty account.

| Column | Meaning |
|---|---|
| customer_id | Account number |
| full_name, email, phone | As the customer entered them |
| created_at | When the account was created |
| home_store_id | The customer's usual store |
| loyalty_points | Points balance |
| marketing_opt_in | 1 or 0 |

All emails use example.com, .net or .org, and all phone numbers are in the fictional 555-01xx range.

## Watch out for

| Problem | How to spot it | How many |
|---|---|---|
| Orders already counted by the tills | Every completed order is also a till check (1,637 at MICROS stores, 631 at Aloha stores) | 2,268 |
| Cancelled orders | `status = cancelled`; they never reached a till and aren't sales | 34 |
| Duplicate customer accounts | Same person, two accounts: name in capitals or as initials, a different email, the phone written differently | 145 people |
| One-cent differences | On Aloha orders the app works out tax from pre-tax prices while Aloha works backwards from tax-inclusive ones, so net sales can differ by a cent | 100 orders |
