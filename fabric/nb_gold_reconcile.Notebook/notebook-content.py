# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "767bc30b-8fb4-4c88-9725-7632324e8d58",
# META       "default_lakehouse_name": "lh_polarslice",
# META       "default_lakehouse_workspace_id": "da1f0187-3dda-4161-8865-ad46eb27457b",
# META       "known_lakehouses": [
# META         {
# META           "id": "767bc30b-8fb4-4c88-9725-7632324e8d58"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Gold: source reconciliation
# Reconciles corrected Gold back to Silver source totals and documents
# the step-by-step exclusions that bridge the two. Also documents
# formula equivalence between SliceDW legacy SQL and nb_gold_legacy.
# Does not rewrite any prior milestone table.

# PARAMETERS CELL ********************

batch_id = ""
period_start = "2026-03-09"
period_end = "2026-03-13"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import uuid
from pyspark.sql import Window, functions as F

BATCH_ID = batch_id or str(uuid.uuid4())
spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

def save(df, table):
    assert table.startswith("reconcile_"), f"Refusing to overwrite non-reconcile table: {table}"
    df = df.withColumn("_gold_batch_id", F.lit(BATCH_ID))
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"gold.{table}"))
    result = spark.table(f"gold.{table}")
    result.createOrReplaceTempView(f"gr_{table}")
    print(f"gold.{table}: {result.count()} rows")

for t in ("corrected_fact_checks", "corrected_daily_sales"):
    b = spark.table(f"gold.{t}").select("_gold_batch_id").distinct().collect()
    assert len(b) == 1 and b[0][0], f"gold.{t}: expected one batch, found {b}"
    print(f"gold.{t}: batch {b[0][0]}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- MICROS reconciliation ---
# Apply the same exclusion logic as nb_gold_corrected to Silver source,
# then verify the resulting amount matches corrected_fact_checks.MICROS exactly.

# Step 1: canonical dedup — keep one row per (store_id, business_date, check_no, void_flag).
# Silver asserts 24 is_duplicate_check rows; canonical keeps the earliest by source_file+batch_id.
# Load all dates so void reversals outside the period can still cancel in-period originals.
(spark.table("silver.micros_checks")
    .withColumn("_rank", F.row_number().over(
        Window.partitionBy("store_id", "business_date", "check_no", "void_flag")
              .orderBy("_source_file", "_batch_id")))
    .filter(F.col("_rank") == 1)
    .drop("_rank")
    .createOrReplaceTempView("gr_micros_canonical"))

assert spark.sql("SELECT * FROM gr_micros_canonical WHERE void_flag NOT IN ('N','V')").count() == 0, \
    "Unexpected MICROS void flag"

# Verify void reversals are exact whole-check cancellations
assert spark.sql("""
    SELECT v.* FROM gr_micros_canonical v LEFT JOIN gr_micros_canonical h
      ON h.store_id = v.store_id AND h.business_date = v.business_date
     AND h.check_no = v.check_no AND h.void_flag = 'N'
    WHERE v.void_flag = 'V'
      AND (h.check_no IS NULL OR
           v.subtotal <> -h.subtotal OR v.discount <> -h.discount OR
           v.tax <> -h.tax OR v.tip <> -h.tip OR v.total <> -h.total)
""").count() == 0, "MICROS void is not an exact whole-check reversal"

# Step 2: in-period N-flag checks, remove gifts, remove void-matched originals
spark.sql(f"""
    SELECT h.store_id, h.business_date, h.check_no,
           CAST(h.check_no AS STRING) AS check_id,
           h.subtotal AS gross, h.discount,
           h.subtotal - h.discount AS net_sales,
           h.tax, h.tip, h.total, h.tender, h.order_type, h.online_ref,
           h.is_gift_check, h.is_duplicate_check
    FROM gr_micros_canonical h
    LEFT ANTI JOIN (
        SELECT store_id, business_date, check_no FROM gr_micros_canonical WHERE void_flag = 'V'
    ) v ON v.store_id = h.store_id AND v.business_date = h.business_date AND v.check_no = h.check_no
    WHERE h.void_flag = 'N'
      AND NOT h.is_gift_check
      AND h.business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").createOrReplaceTempView("gr_micros_silver_sales")

micros_silver_sum = float(spark.sql("SELECT SUM(net_sales) FROM gr_micros_silver_sales").collect()[0][0] or 0)
micros_gold_sum   = float(spark.sql("SELECT SUM(net_sales) FROM gold.corrected_fact_checks WHERE source_system='MICROS'").collect()[0][0] or 0)
micros_residual   = micros_silver_sum - micros_gold_sum
print(f"MICROS silver_sales={micros_silver_sum:,.2f}  corrected_gold={micros_gold_sum:,.2f}  residual={micros_residual:,.2f}")
assert abs(micros_residual) <= 0.02, f"MICROS reconciliation residual {micros_residual:.4f} exceeds tolerance"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Aloha reconciliation ---
# Silver stores net_sales_excl_tax = net_total_tax_incl - tax (no rounding applied in Silver).
# Corrected Gold uses c.net_sales_excl_tax directly, with the same DOB period filter.
# Silver Aloha asserts unique (store_id, business_date, check_id), so no dedup needed.

spark.sql(f"""
    SELECT store_id, business_date, check_id,
           net_sales_excl_tax AS net_sales,
           net_total_tax_incl, tax, comp_tax_incl,
           is_after_midnight
    FROM silver.aloha_checks
    WHERE business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").createOrReplaceTempView("gr_aloha_silver_sales")

aloha_silver_sum = float(spark.sql("SELECT SUM(net_sales) FROM gr_aloha_silver_sales").collect()[0][0] or 0)
aloha_gold_sum   = float(spark.sql("SELECT SUM(net_sales) FROM gold.corrected_fact_checks WHERE source_system='ALOHA'").collect()[0][0] or 0)
aloha_residual   = aloha_silver_sum - aloha_gold_sum
print(f"ALOHA  silver_sales={aloha_silver_sum:,.2f}  corrected_gold={aloha_gold_sum:,.2f}  residual={aloha_residual:,.2f}")
assert abs(aloha_residual) <= 0.02, f"Aloha reconciliation residual {aloha_residual:.4f} exceeds tolerance"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Cross-system balance ---
# Corrected Gold adds no app revenue. MICROS + Aloha corrected = corrected period total.

period_total = float(spark.sql("SELECT SUM(net_sales) FROM gold.corrected_daily_sales").collect()[0][0] or 0)
cross_system = micros_gold_sum + aloha_gold_sum
cross_residual = cross_system - period_total
print(f"MICROS corrected: {micros_gold_sum:,.2f}")
print(f"ALOHA  corrected: {aloha_gold_sum:,.2f}")
print(f"Sum:              {cross_system:,.2f}")
print(f"Period total:     {period_total:,.2f}")
print(f"Residual:         {cross_residual:,.2f}")
assert abs(cross_residual) <= 0.02, f"Cross-system residual {cross_residual:.4f} exceeds tolerance"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Anomaly summary table ---
# Count and amount for each exclusion reason: gift checks, void reversals and
# their matched originals, duplicate surplus, Aloha tax-inclusive delta.

silver_all_n = spark.sql(f"""
    SELECT store_id, business_date, check_no, subtotal - discount AS net_sales,
           is_gift_check, is_duplicate_check, is_void_reversal
    FROM gr_micros_canonical
    WHERE void_flag = 'N'
      AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""")
silver_all_n.createOrReplaceTempView("gr_micros_all_n")

void_keys = spark.sql(
    "SELECT DISTINCT store_id, business_date, check_no FROM gr_micros_canonical WHERE void_flag = 'V'"
)
void_keys.createOrReplaceTempView("gr_void_keys")

rows = []

# Gift checks
g = spark.sql("SELECT COUNT(*) AS n, SUM(net_sales) AS amt FROM gr_micros_all_n WHERE is_gift_check").collect()[0]
rows.append(("MICROS_GIFT_EXCLUDED", int(g.n), float(g.amt or 0),
             "MICROS gift-load checks (order_type=GIFT) excluded from revenue; gift-card tender on a genuine sale stays in"))

# Void-matched original checks
vm = spark.sql("""
    SELECT COUNT(*) AS n, SUM(net_sales) AS amt FROM gr_micros_all_n m
    JOIN gr_void_keys v ON v.store_id=m.store_id AND v.business_date=m.business_date AND v.check_no=m.check_no
    WHERE NOT m.is_gift_check
""").collect()[0]
rows.append(("MICROS_VOID_EXCLUDED", int(vm.n), float(vm.amt or 0),
             "MICROS original checks (void_flag=N) where an exact reversal (void_flag=V) exists; both sides excluded"))

# Void reversal rows (V-flag)
vv = spark.sql(f"""
    SELECT COUNT(*) AS n, SUM(-subtotal) AS amt FROM gr_micros_canonical
    WHERE void_flag = 'V' AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").collect()[0]
rows.append(("MICROS_VOID_REVERSAL_ROWS", int(vv.n), float(vv.amt or 0),
             "MICROS void-reversal rows (void_flag=V) — reversal amounts shown for reference; excluded from sales"))

# Duplicate surplus rows (rows in Silver not surviving dedup)
# Count by comparing Silver row count to canonical row count
silver_n_count  = spark.sql(f"""
    SELECT COUNT(*) AS n FROM silver.micros_checks
    WHERE void_flag='N' AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").collect()[0].n
canonical_n_count = spark.sql(f"""
    SELECT COUNT(*) AS n FROM gr_micros_canonical
    WHERE void_flag='N' AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").collect()[0].n
dup_count = int(silver_n_count) - int(canonical_n_count)
dup_amt = float(spark.sql(f"""
    SELECT SUM(subtotal - discount) AS amt FROM silver.micros_checks s
    WHERE void_flag='N' AND is_duplicate_check
      AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
      AND NOT EXISTS (
          SELECT 1 FROM gr_micros_canonical c
          WHERE c.store_id=s.store_id AND c.business_date=s.business_date
            AND c.check_no=s.check_no AND c.void_flag='N'
            AND c._source_file=s._source_file AND c._batch_id=s._batch_id
      )
""").collect()[0].amt or 0)
rows.append(("MICROS_DUPLICATE_SURPLUS", dup_count, dup_amt,
             "Surplus copies of duplicated MICROS checks (same store/date/check_no); earliest copy retained in corrected"))

# Aloha tax correction
aloha_tax_incl = float(spark.sql(f"""
    SELECT SUM(net_total_tax_incl) FROM silver.aloha_checks
    WHERE business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").collect()[0][0] or 0)
aloha_tax_delta = aloha_tax_incl - aloha_silver_sum
aloha_check_count = int(spark.sql(f"""
    SELECT COUNT(*) FROM silver.aloha_checks
    WHERE business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").collect()[0][0])
rows.append(("ALOHA_TAX_INCLUSIVE_TO_EXCLUSIVE", aloha_check_count, aloha_tax_delta,
             "Aloha net_sales converted from tax-inclusive (NETTOTAL) to tax-exclusive (NETTOTAL-TAXINCL); 13% HST removed"))

# Aloha after-midnight boundary (checks with DOB in period but close_ts outside — present in corrected, absent in legacy)
after_midnight_in = spark.sql(f"""
    SELECT COUNT(*) AS n, SUM(net_sales_excl_tax) AS amt FROM silver.aloha_checks
    WHERE business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
      AND is_after_midnight AND to_date(close_ts) > DATE '{period_end}'
""").collect()[0]
rows.append(("ALOHA_CLOSE_OUTSIDE_PERIOD", int(after_midnight_in.n), float(after_midnight_in.amt or 0),
             "After-midnight Aloha checks (DOB in period, close_ts after period end); in corrected, absent from legacy"))

after_midnight_out = spark.sql(f"""
    SELECT COUNT(*) AS n, SUM(net_total_tax_incl) AS amt FROM silver.aloha_checks
    WHERE business_date < DATE '{period_start}'
      AND is_after_midnight AND to_date(close_ts) BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").collect()[0]
rows.append(("ALOHA_DOB_OUTSIDE_PERIOD", int(after_midnight_out.n), float(after_midnight_out.amt or 0),
             "After-midnight Aloha checks (DOB before period start, close_ts in period); in legacy, absent from corrected"))

anomaly_df = (spark.createDataFrame(rows, "category STRING, check_count INT, net_sales_impact DOUBLE, description STRING")
              .withColumn("net_sales_impact", F.col("net_sales_impact").cast("DECIMAL(19,4)")))
save(anomaly_df, "reconcile_anomaly_summary")

for row in anomaly_df.orderBy("category").collect():
    print(f"  {row.category}: {row.check_count} checks, {float(row.net_sales_impact):+,.2f} net_sales_impact")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Daily cross-system detail table ---
# Per store/date: Silver MICROS sales + Silver Aloha sales vs corrected_daily_sales.
# Residual should be zero across all 50 store/dates.

save(spark.sql(f"""
    SELECT COALESCE(m.store_id, a.store_id) AS store_id,
           COALESCE(m.business_date, a.business_date) AS business_date,
           COALESCE(m.micros_net_sales, 0) AS silver_micros_net_sales,
           COALESCE(a.aloha_net_sales, 0) AS silver_aloha_net_sales,
           COALESCE(m.micros_net_sales, 0) + COALESCE(a.aloha_net_sales, 0) AS silver_combined_net_sales,
           COALESCE(d.net_sales, 0) AS corrected_daily_net_sales,
           COALESCE(m.micros_net_sales, 0) + COALESCE(a.aloha_net_sales, 0) - COALESCE(d.net_sales, 0) AS residual
    FROM (
        SELECT store_id, business_date, SUM(net_sales) AS micros_net_sales
        FROM gr_micros_silver_sales GROUP BY store_id, business_date
    ) m
    FULL OUTER JOIN (
        SELECT store_id, business_date, SUM(net_sales) AS aloha_net_sales
        FROM gr_aloha_silver_sales GROUP BY store_id, business_date
    ) a ON a.store_id = m.store_id AND a.business_date = m.business_date
    FULL OUTER JOIN gold.corrected_daily_sales d
      ON d.store_id = COALESCE(m.store_id, a.store_id)
     AND d.business_date = COALESCE(m.business_date, a.business_date)
"""), "reconcile_daily_cross_system")

max_residual = float(spark.sql("SELECT MAX(ABS(residual)) FROM gr_reconcile_daily_cross_system").collect()[0][0] or 0)
print(f"Max per-store-day residual: {max_residual:,.4f}")
assert max_residual <= 0.02, f"Cross-system daily residual {max_residual:.4f} exceeds tolerance"
spark.table("gold.reconcile_daily_cross_system").orderBy("store_id", "business_date").show(60, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- SliceDW formula equivalence documentation ---
# Documents that nb_gold_legacy reproduces SliceDW (02_programmability.sql) formula-for-formula.
# Sources: analysis of SliceDW SQL vs nb_gold_legacy.Notebook/notebook-content.py.

slicedw_rows = [
    ("MICROS void filter",
     "WHERE void_flag = 'N'",
     "WHERE void_flag = 'N'",
     "MATCH",
     "Both exclude void-reversal rows; original checks voided by a matching V-row remain in legacy sales"),
    ("MICROS net sales per check",
     "subtotal - discount",
     "subtotal - discount AS net_sales",
     "MATCH",
     ""),
    ("Aloha net sales per check",
     "c.nettotal (tax-inclusive NETTOTAL)",
     "net_total_tax_incl (Silver alias for NETTOTAL)",
     "MATCH",
     "KNOWN DEFECT: tax-inclusive amount used as net sales; corrected uses net_total_tax_incl - tax"),
    ("Daily net sales formula",
     "net_sales_tills + online_only_sales",
     "COALESCE(net_sales_tills,0) + COALESCE(online_only_sales,0)",
     "MATCH",
     "KNOWN DEFECT: app online_only_sales added as revenue; corrected treats app as attribution-only"),
    ("Online order dedup",
     "WHERE is_duplicate_of_pos = 0",
     "WHERE NOT is_duplicate_of_pos",
     "MATCH",
     ""),
    ("Royalty rate application",
     "ROUND(net_sales * 0.05, 2)",
     "round(CAST(net_sales AS DECIMAL(19,4)) * CAST('0.05' AS DECIMAL(9,4)), 2)",
     "MATCH",
     ""),
    ("Ad fund rate application",
     "ROUND(net_sales * 0.03, 2)",
     "round(CAST(net_sales AS DECIMAL(19,4)) * CAST('0.03' AS DECIMAL(9,4)), 2)",
     "MATCH",
     ""),
    ("New store royalty holiday",
     "open_date <= DATEADD(MONTH, -3, @PeriodEnd)  [hardcoded -3, ignores NEW_STORE_HOLIDAY_MONTHS term]",
     "open_date <= add_months(DATE period_end, -3)  [reproduces -3 bug intentionally]",
     "MATCH (bug reproduced)",
     "KNOWN DEFECT: SQL ignores the NEW_STORE_HOLIDAY_MONTHS=6 term; uses -3. Corrected uses the term (6 months)"),
    ("Food variance: theoretical",
     "SUM(qty_sold * qty_per_unit) FROM FactCheckLine JOIN Recipe",
     "SUM(l.qty * r.qty_per_unit) FROM corrected_fact_check_lines l JOIN recipes r",
     "MATCH",
     "KNOWN DEFECT in legacy: gift and void check lines included in theoretical use; corrected excludes them"),
    ("Food variance: commissary receipts",
     "qty_cases * pack_qty  (cases only, unsigned)",
     "quantity_base_units  (signed: credits carry negative quantity from Silver)",
     "DIFFERS",
     "KNOWN DEFECT: SliceDW converts qty_cases * pack_qty, missing credits and KG-unit items. Corrected uses signed base-unit quantities from Silver"),
    ("Variance %",
     "ROUND(variance / theoretical * 100, 1)",
     "CAST(round(variance/theoretical_usage * 100, 1) AS DECIMAL(12,1))",
     "MATCH",
     "NULL when theoretical = 0"),
    ("Variance cost",
     "ROUND(variance * pack_cost / pack_qty, 2)",
     "round(variance * CAST(pack_cost AS DECIMAL(19,4)) / pack_qty, 2)",
     "MATCH",
     ""),
]

slicedw_df = spark.createDataFrame(
    slicedw_rows,
    "metric STRING, slicedw_formula STRING, gold_formula STRING, equivalence STRING, notes STRING"
)
save(slicedw_df, "reconcile_slicedw")
spark.table("gold.reconcile_slicedw").orderBy("metric").show(truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Final verification summary ---
print("=== Reconciliation summary ===")
print(f"MICROS: Silver→corrected residual: {micros_residual:+,.2f}")
print(f"ALOHA:  Silver→corrected residual: {aloha_residual:+,.2f}")
print(f"Cross-system (MICROS+ALOHA vs daily): {cross_residual:+,.2f}")
print(f"Max per-store-day residual: {max_residual:,.4f}")
print(f"Batch: {BATCH_ID}")
if (period_start, period_end) == ("2026-03-09", "2026-03-13"):
    expected = {
        "reconcile_anomaly_summary": 7,
        "reconcile_daily_cross_system": 50,
        "reconcile_slicedw": 12,
    }
    for table, exp in expected.items():
        actual = spark.table(f"gold.{table}").count()
        assert actual == exp, f"gold.{table}: expected {exp} rows, found {actual}"
print("All reconciliation checks passed.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
