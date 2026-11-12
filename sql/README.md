# Azure SQL deployment — Corrected Gold Mart

Deploys the corrected Polar Slice Pizza Gold mart to Azure SQL Database.
Target: a single-period snapshot of the week 2026-03-09 to 2026-03-13.

## Prerequisites

- Azure SQL Database (Basic tier or above)
- Access to the Fabric workspace `lh_polarslice` (corrected Gold run confirmed successful)
- Fabric Pipeline or ADF for export, or access to export CSVs manually

## Scripts

| File | Purpose |
|---|---|
| `01_schema.sql` | Creates `gold` schema and all 11 corrected mart tables |
| `02_load_procedures.sql` | Creates `stg` staging tables and `gold.usp_LoadCorrectedGold` |
| `03_validation.sql` | Post-load assertions and spot-check queries |

## Execution order

Run these scripts in order against the target Azure SQL Database:

```sql
-- 1. Create schema and tables
:r 01_schema.sql

-- 2. Create staging and load procedure
:r 02_load_procedures.sql

-- 3. Load data (see Export section below), then validate
:r 03_validation.sql
```

## Exporting from Fabric

Each corrected Gold table must be exported from Fabric before loading.

**Option A — Fabric Pipeline (recommended):**
1. In the Fabric workspace, create a Pipeline with Copy activities from each `gold.corrected_*` Delta table to Azure Blob Storage as CSV (UTF-8, header row, comma delimiter, `"` quote character).
2. Use BULK INSERT to load from blob into the corresponding `stg.corrected_*` staging table.

**Option B — CETAS via Spark (from a Fabric notebook):**
```python
for table in [
    "corrected_run_inputs", "corrected_promo_cost", "corrected_fact_checks",
    "corrected_fact_check_lines", "corrected_online_attribution", "corrected_daily_sales",
    "corrected_adjustment_decisions", "corrected_royalty_invoices",
    "corrected_food_cost_variance", "corrected_region_daily_sales",
    "corrected_franchisee_invoices",
]:
    (spark.table(f"gold.{table}")
     .write.mode("overwrite").option("header", True)
     .csv(f"abfss://<container>@<account>.dfs.core.windows.net/export/gold/{table}"))
```

**BULK INSERT example (per table):**
```sql
BULK INSERT stg.corrected_fact_checks
FROM 'https://<account>.blob.core.windows.net/export/gold/corrected_fact_checks/part-00000.csv'
WITH (
    DATA_SOURCE = 'YourExternalDataSource',
    FORMAT = 'CSV',
    FIRSTROW = 2,
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '\n',
    TABLOCK
);
```

## Loading and validating

After all staging tables are populated, call the load procedure:

```sql
EXEC gold.usp_LoadCorrectedGold
    @period_start  = '2026-03-09',
    @period_end    = '2026-03-13',
    @gold_batch_id = '175fdd4c-8417-4a00-b951-f563f4d533fd';  -- Fabric corrected Gold batch
```

The procedure:
1. Verifies staging row counts against archived Fabric baselines
2. Wraps the truncate + insert in a transaction
3. Spot-checks period net sales ($268,893.08) and invoice total ($17,251.74)
4. Throws an informative error if any check fails; rolls back on transaction error

Then run `03_validation.sql` for the full set of post-load assertions.

## Expected results

| Table | Rows |
|---|---:|
| `corrected_run_inputs` | 15 |
| `corrected_promo_cost` | 69 |
| `corrected_fact_checks` | 9,231 |
| `corrected_fact_check_lines` | 25,664 |
| `corrected_online_attribution` | 2,302 |
| `corrected_daily_sales` | 50 |
| `corrected_adjustment_decisions` | 5 |
| `corrected_royalty_invoices` | 8 |
| `corrected_food_cost_variance` | 190 |
| `corrected_region_daily_sales` | 85 |
| `corrected_franchisee_invoices` | 6 |

Period net sales: **$268,893.08** | Invoice total: **$17,251.74**

Store 1078 has no royalty invoice (6-month new-store holiday; `03_validation.sql` asserts this).

## Re-deployment

Re-running `01_schema.sql` drops and recreates all tables. Run the full sequence (01 → 02 → load → 03) to redeploy from a fresh export.
