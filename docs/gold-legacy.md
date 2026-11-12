# Gold milestone 1: reference inputs and legacy reproduction

## Scope and status

This milestone reproduces SliceDW's March 9-13, 2026 facts and reports **without correcting its business defects**. It adds three Git-synced Fabric notebooks:

- `nb_gold_reference_data`: writes four versioned reference snapshots.
- `nb_gold_legacy`: writes the legacy facts, reports, and input manifest.
- `nb_gold_run_legacy`: executes those two notebooks in order with one Gold batch ID.

Local PySpark execution passed against the committed source pack. Every keyed report row was compared to an independent Python/Decimal calculation of the legacy SQL rules. This is not yet a live Fabric run or a comparison against deployed SQL Server/answer-key exports. Corrected Gold and formal reconciliation are not implemented in this milestone.

## Fabric execution

1. Keep the workspace Git connection on `NG/Dev`, directory `/fabric`, and update from source control. Do not switch to a branch without the lakehouse item.
2. Confirm the successful Silver run is still present. All required Silver tables must share one non-empty `_silver_batch_id`. If individual Silver notebooks have since been rerun separately, run `nb_silver_run_all` again first.
3. Open `nb_gold_run_legacy`, confirm `lh_polarslice` is its default lakehouse, and use the defaults `period_start = "2026-03-09"` and `period_end = "2026-03-13"`.
4. Run all cells. The runner invokes the reference notebook and then the legacy notebook with `useRootDefaultLakehouse: True`. It prints each output count, daily totals, invoices, and cheese variance.
5. Capture the Gold batch ID, notebook statuses, counts, and report output. Review them before approving the next milestone.

If Gold reports mixed Silver batches, inspect the Silver runner's batch validation output. Each Silver output must contain exactly the ID printed by that runner. Silver and Gold parameter cells must be recognized by Fabric as parameter cells (`# PARAMETERS CELL ********************` in the Git source); ordinary cells with parameter tags do not provide the native source marker. After syncing this fix, rerun Silver before Gold. Do not relabel existing batches or remove the consistency guard.

No new file upload is required. Reference snapshots are embedded in the reference notebook so they travel through Fabric Git; their authoritative source is `data/2_legacy_warehouse_slicedw/sql/03_reference_data.sql`. The adjustment records are also present in `ManualAdjustments_March2026.csv`.

Writes use Delta overwrite with schema replacement. Reruns replace this milestone's output snapshot, **not individual historical partitions**. A custom period must have its boundaries in the Silver calendar. `legacy_shipments`, `legacy_stock_counts`, and item dimensions contain the full input extracts, as `usp_LoadCommissary` does; period filters are applied in the reports. The default-period row-count assertions are specific to this source pack.

Multi-table publication is not transactional: a failed run can leave some outputs from the new batch and others from an older run. Treat the outputs as consumable only after both notebooks succeed; rerun the legacy runner after resolving an error. Bronze and Silver are not modified.

## Reference contracts

| Gold table | Rows | Source and treatment |
|---|---:|---|
| `reference_royalty_terms` | 3 | Royalty 5%, ad fund 3%, six-month contractual holiday. Legacy intentionally ignores the holiday term and uses three months. |
| `reference_org_units` | 17 | Company, two regions, four districts, and ten store nodes. |
| `reference_legacy_aloha_map` | 15 | Original incomplete map, including `MDVEG -> PZ-VEG-L`. Not Silver's corrected mapping. |
| `reference_manual_adjustments` | 5 | Stable source-order IDs; both copies of the $120 Square One credit retained and flagged. |

References carry `_reference_source`, `_reference_version`, and `_gold_batch_id`. Update the snapshots and their version together if authoritative inputs change. Regression tests compare them with the SQL reference inputs; do not manually change a legacy mapping to its corrected value.

## Legacy rules and their dependencies

| SliceDW procedure/view | Output | Faithfully retained behavior |
|---|---|---|
| `usp_LoadFactCheckMicros` | `legacy_fact_checks`, `legacy_fact_check_lines` | Header `void_flag = N`; gifts and duplicated polls retained. Lines use `ITEM`/`GIFT` only and the MICROS menu map. |
| `usp_LoadFactCheckAloha` | Same check/line facts | Reporting day is check close date, not DOB. `NETTOTAL`, gross, and comps remain tax-inclusive. Lines use the legacy Aloha map, including null/wrong SKUs. |
| `usp_LoadFactOnline`, `usp_DedupOnline` | `legacy_fact_online_orders` | Order's local calendar date, `status <> refunded` (thus cancellations retained); dedupe only by MICROS store/date/check number. Silver's improved links are ignored. Six March 14 orders are outside the legacy period. |
| `usp_BuildNetSales` | `legacy_daily_sales` | Till sales plus unmatched online sales. Void amounts are displayed but not subtracted from net sales. Counts include legacy gift and duplicate check rows. |
| `usp_BuildPromoCost` | `legacy_promo_cost` | MICROS discounts by business date; Aloha comps by order timestamp date and with tax included. |
| `usp_LoadCommissary` | `legacy_dim_items`, `legacy_shipments`, `legacy_stock_counts` | All shipment quantities treated as cases; trailing credit signs ignored. Unsigned costs recovered from retained `ext_cost_raw`, not Silver's signed cost/base-unit quantities. |
| `usp_CalcRoyalty` | `legacy_royalty_invoices` | Franchise-only invoices; three-month cutoff at period end; both adjustment copies included; royalty and ad fund rounded separately to cents. Store 1078 is therefore invoiced. |
| `usp_CalcFoodCost` | `legacy_food_cost_variance` | Opening + case-assumed receipts - closing; theoretical usage from legacy line SKUs and recipes. Percent null where theoretical usage is zero. |
| `usp_BuildRegionRollup` | `legacy_region_daily_sales` | Ancestor closure includes store self-rows, districts, regions, and company. Missing parents, cycles, and depth beyond the legacy recursion limit fail explicitly. |
| `vw_FranchiseeInvoice` | `legacy_franchisee_invoices` | Franchisee totals over legacy store invoices. |
| `vw_StoreDaySales` | `legacy_store_day_sales` | Store/day/source sums and check counts over the legacy check facts. |

`legacy_daily_sales` retains the fact table's business columns; join to `silver.stores` for the store labels supplied by SliceDW's `vw_DailySales`. `legacy_run_inputs` records each of the 16 dependency tables, its input batch ID, row count, and selected period. Facts retain available file/Bronze/Silver lineage. All outputs have `_gold_batch_id` and `_rules_version`.

SQL identity IDs, `GETDATE()` values, trigger/audit simulation, staging purge, and ETL log timestamps are not business report values and are not emulated. These belong to the later Azure SQL/dossier phase. Tender sets are serialized in sorted order instead of reproducing the unspecified `FOR XML PATH` ordering.

## Local baseline evidence

These counts and totals were calculated from the committed sources and validated by local Spark, **not copied from an answer key**:

| Legacy output | Rows |
|---|---:|
| `legacy_fact_checks` | 9,269 |
| `legacy_fact_check_lines` | 25,681 |
| `legacy_fact_online_orders` | 2,296 |
| `legacy_daily_sales` | 50 |
| `legacy_promo_cost` | 72 |
| `legacy_dim_items` | 19 |
| `legacy_shipments` | 564 |
| `legacy_stock_counts` | 380 |
| `legacy_royalty_invoices` | 9 |
| `legacy_food_cost_variance` | 190 |
| `legacy_region_daily_sales` | 85 |
| `legacy_franchisee_invoices` | 7 |
| `legacy_store_day_sales` | 50 |
| `legacy_run_inputs` | 16 |

Period legacy net sales: **$299,572.90**. Invoice amount due: **$21,061.48**. Promo discounts: **$20,975.38**. Food variance cost across all ingredients: **$123,456.13**. These intentionally incorrect legacy values are a migration baseline, not approved business results.

| Day | Legacy net sales |
|---|---:|
| 2026-03-09 | $47,906.41 |
| 2026-03-10 | $65,533.77 |
| 2026-03-11 | $50,141.53 |
| 2026-03-12 | $55,974.53 |
| 2026-03-13 | $80,016.66 |

The tests execute actual notebook transformations and validations, using local Parquet table writes in place of Fabric Delta writes. They compare every business metric in the daily, promo, royalty, food-cost, regional, franchisee, and store/day/source reports. All 190 food-cost rows match the independent Decimal baseline exactly, with no rounding tolerance. The legacy README cautions that a live SQL Server comparison might expose a one-cent rounding difference: investigate such a difference explicitly rather than silently accepting it.

With Java 17 and PySpark 3.5 installed, run:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

No generators are executed, and no answer-key files are read or generated. External SliceDW/answer-key comparison remains pending. Preserve the one ambiguous Aloha online match for the corrected/reconciliation milestone; legacy reproduction deliberately does not use it.
