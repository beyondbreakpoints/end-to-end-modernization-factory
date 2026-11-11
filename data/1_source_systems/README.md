# 1. Source systems

The files from Polar Slice's legacy sources, as their nightly exports deliver them. This is what the Fabric pipeline loads into Bronze. Each folder has a README describing its files and their quirks.

| Folder | System | Format | Files |
|---|---|---|---|
| `master_data/` | Head office reference data | CSV | Stores, menu, calendar, recipes |
| `micros/` | Oracle MICROS RES 3700 tills (7 original stores) | Pipe-delimited text | One header file and one detail file per day |
| `aloha/` | NCR Aloha tills (3 stores acquired in 2022) | CSV | One folder per store per business day |
| `online_app/` | Custom online ordering and loyalty app | JSON and CSV | Orders per day, plus customer accounts |
| `as400_commissary/` | IBM i (AS/400) commissary system | Fixed-width text | Item master, shipments, stock counts, plus COBOL copybooks |

When setting up copy jobs, filter by the data file patterns (`*.txt`, `*.csv`, `*.json`, `*.TXT`) so the README files aren't loaded as data.

## How the systems relate

- **Tills are the system of record for sales.** MICROS and Aloha record every sale, including orders placed online.
- **The online app duplicates the tills.** Every completed app order is also a till check. MICROS checks carry the app's order ID (`online_ref`) and the app carries the MICROS check number (`pos_check_no`). Aloha has no link in either direction.
- **The commissary connects through recipes.** Theoretical ingredient use = what the tills sold × `master_data/recipes.csv`. Actual use comes from the commissary's shipments and stock counts.
- **Head office's menu is the common product list.** MICROS item numbers map to it directly; Aloha codes don't.

## Common ground

- Every store, product and date appears consistently across all systems.
- All stores are in Ontario: tax is 13% HST, and the time zone is Eastern (UTC−04:00 in this period).
- All names, emails and phone numbers are fictional (example.com addresses, 555-01xx numbers).
