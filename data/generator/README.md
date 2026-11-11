# 4. Generator

The Python scripts that produced every data file in this pack. You only need these to regenerate the data or make a bigger data set.

Requires Python 3, no extra packages. From this folder, run them in this order:

```
python3 generate_master.py ..
python3 generate_micros.py ..
python3 generate_aloha.py ..
python3 generate_online.py ..
python3 generate_commissary.py ..
python3 generate_slicedw.py ..
```

The order matters: the online app and the commissary are built from what the tills sold, and SliceDW from everything. The `..` tells each script where the pack's root folder is.

The output is the same on every run (fixed random seeds), so regenerating gives identical files.

| Script | Writes |
|---|---|
| `common.py` | Not run directly: shared settings, stores, menu, and the folder layout (`P`) |
| `generate_master.py` | `master_data/` stores, menu and calendar, and `menu_crosswalk.csv` |
| `generate_micros.py` | `micros/` and the MICROS answer-key files |
| `generate_aloha.py` | `aloha/` and the Aloha answer-key files |
| `generate_online.py` | `online_app/` and the online answer-key files |
| `generate_commissary.py` | `as400_commissary/`, `master_data/recipes.csv` and the commissary answer-key files |
| `generate_slicedw.py` | SliceDW's `03`, `04` and `05` SQL scripts, the SSIS packages, the adjustments spreadsheet, and SliceDW's legacy numbers in the answer key |

`01_schema.sql` and `02_programmability.sql` are written by hand and aren't regenerated. If you change a stored procedure, change its Python copy in `generate_slicedw.py` to match, or SliceDW's answer-key numbers will no longer agree with the database.

## Making a bigger data set

Edit `common.py`:

- `START_DATE` and `NUM_DAYS` set the date range. About 3 months is enough for every measure, including same-store sales growth, which needs a comparison period.
- `STORES` lists the stores; add rows to add stores.

Generate into a new, empty folder so old files don't linger: copy this `4_generator` folder into the new folder, plus `2_legacy_warehouse_slicedw/sql/01_schema.sql` and `02_programmability.sql` into a `2_legacy_warehouse_slicedw/sql` folder, then run the scripts with `..`. Some details are tuned to the 5-day dev slice and should be checked when scaling up: the planted re-sent checks (`DUPLICATE_POLL` in `generate_micros.py`), the royalty period in `generate_slicedw.py`, and the commissary's two stock counts (start and end of the period).
