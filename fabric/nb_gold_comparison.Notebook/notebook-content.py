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

# # Gold: legacy-to-corrected comparison bridge
# Reads gold.legacy_* and gold.corrected_* to produce a check-level bridge and period waterfall.
# Shows exactly which checks were added, removed, or revalued and why the totals differ.
# Does not rewrite legacy, corrected, or reference tables.

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
from pyspark.sql import functions as F

BATCH_ID = batch_id or str(uuid.uuid4())
spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

def save(df, table):
    assert table.startswith("comparison_"), f"Refusing to overwrite non-comparison output: {table}"
    df = df.withColumn("_gold_batch_id", F.lit(BATCH_ID))
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"gold.{table}"))
    result = spark.table(f"gold.{table}")
    result.createOrReplaceTempView(f"gb_{table}")
    print(f"gold.{table}: {result.count()} rows")

for t in ("legacy_fact_checks", "corrected_fact_checks", "legacy_daily_sales", "corrected_daily_sales",
          "legacy_royalty_invoices", "corrected_royalty_invoices"):
    b = spark.table(f"gold.{t}").select("_gold_batch_id").distinct().collect()
    assert len(b) == 1 and b[0][0], f"gold.{t}: expected one non-empty batch, found {b}"
    print(f"gold.{t}: batch {b[0][0]}")

spark.table("silver.micros_checks").createOrReplaceTempView("gb_sm")
spark.table("silver.aloha_checks").createOrReplaceTempView("gb_sa")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- MICROS bridge ---
# Legacy includes gift checks, both sides of void pairs, and duplicate rows (24 in Silver).
# Corrected excludes gifts, void-matched pairs, and deduplicates to one row per check_id.
# Aggregate legacy by (store_id, business_date, check_id) BEFORE joining: a check that
# appears twice in legacy_fact_checks contributes 2X to the legacy total. Without the
# aggregation a FULL OUTER JOIN (2 legacy rows × 1 corrected row) would produce 2 bridge
# rows and compute 2(Y-X)=0 instead of Y-2X=-X, hiding the duplicate-check delta.

spark.sql(f"""
    SELECT store_id, business_date, check_id,
           SUM(net_sales) AS legacy_net_sales
    FROM gold.legacy_fact_checks
    WHERE source_system = 'MICROS'
      AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
    GROUP BY store_id, business_date, check_id
""").createOrReplaceTempView("gb_micros_legacy")

spark.sql(f"""
    SELECT store_id, business_date, check_id, net_sales AS corrected_net_sales
    FROM gold.corrected_fact_checks
    WHERE source_system = 'MICROS'
      AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").createOrReplaceTempView("gb_micros_corrected")

spark.sql(f"""
    SELECT COALESCE(l.store_id, c.store_id) AS store_id,
           COALESCE(l.business_date, c.business_date) AS business_date,
           COALESCE(l.check_id, c.check_id) AS check_id,
           COALESCE(l.legacy_net_sales, 0) AS legacy_net_sales,
           COALESCE(c.corrected_net_sales, 0) AS corrected_net_sales,
           COALESCE(c.corrected_net_sales, 0) - COALESCE(l.legacy_net_sales, 0) AS net_sales_delta,
           CASE
               WHEN c.check_id IS NOT NULL AND l.check_id IS NOT NULL THEN 'BOTH'
               WHEN c.check_id IS NULL THEN 'MICROS_LEGACY_ONLY'
               ELSE 'MICROS_CORRECTED_ONLY'
           END AS exclusion_reason,
           'MICROS' AS source_system
    FROM gb_micros_legacy l
    FULL OUTER JOIN gb_micros_corrected c
      ON l.store_id = c.store_id AND l.business_date = c.business_date AND l.check_id = c.check_id
""").createOrReplaceTempView("gb_micros_bridge")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Aloha bridge ---
# Legacy check_id = "YYYYMMDD-CHECKID" where YYYYMMDD is DOB, CHECKID is str(integer).
# Corrected check_id = str(integer), business_date = DOB.
# Join Gold tables directly on (store_id, DOB, CHECKID) — no Silver intermediary,
# so no checks can be dropped by a failed intermediary join.

spark.sql(f"""
    SELECT COALESCE(l.store_id, c.store_id) AS store_id,
           COALESCE(to_date(substr(l.check_id, 1, 8), 'yyyyMMdd'), c.business_date) AS business_date,
           COALESCE(substr(l.check_id, 10), c.check_id) AS check_id,
           COALESCE(l.legacy_net_sales, 0) AS legacy_net_sales,
           COALESCE(c.corrected_net_sales, 0) AS corrected_net_sales,
           COALESCE(c.corrected_net_sales, 0) - COALESCE(l.legacy_net_sales, 0) AS net_sales_delta,
           CASE
               WHEN l.check_id IS NOT NULL AND c.check_id IS NOT NULL
                    AND l.legacy_close_date <> to_date(substr(l.check_id, 1, 8), 'yyyyMMdd')
                    THEN 'ALOHA_DATE_SHIFT'
               WHEN l.check_id IS NOT NULL AND c.check_id IS NOT NULL THEN 'BOTH'
               WHEN c.check_id IS NULL THEN 'ALOHA_DOB_OUTSIDE_PERIOD'
               ELSE 'ALOHA_CLOSE_OUTSIDE_PERIOD'
           END AS exclusion_reason,
           l.legacy_close_date,
           'ALOHA' AS source_system
    FROM (
        SELECT store_id, check_id, net_sales AS legacy_net_sales,
               business_date AS legacy_close_date
        FROM gold.legacy_fact_checks
        WHERE source_system = 'ALOHA'
          AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
    ) l
    FULL OUTER JOIN (
        SELECT store_id, check_id, net_sales AS corrected_net_sales, business_date
        FROM gold.corrected_fact_checks
        WHERE source_system = 'ALOHA'
          AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
    ) c
    ON  l.store_id = c.store_id
    AND substr(l.check_id, 1, 8) = date_format(c.business_date, 'yyyyMMdd')
    AND substr(l.check_id, 10) = c.check_id
""").createOrReplaceTempView("gb_aloha_bridge")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- App adjustment ---
# Legacy adds online_only_sales (app orders not matching POS checks).
# Corrected never adds app amounts; online attribution is evidence-only.

spark.sql(f"""
    SELECT store_id, business_date,
           COALESCE(online_only_sales, 0) AS legacy_app_net_sales,
           CAST(0 AS DECIMAL(19,4)) AS corrected_app_net_sales,
           -COALESCE(online_only_sales, 0) AS net_sales_delta
    FROM gold.legacy_daily_sales
    WHERE business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
      AND online_only_sales <> 0
""").createOrReplaceTempView("gb_app_bridge")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- comparison_bridge: check-level combined bridge ---

bridge = spark.sql("""
    SELECT source_system, store_id, business_date, check_id,
           CAST(legacy_net_sales AS DECIMAL(19,4)) AS legacy_net_sales,
           CAST(corrected_net_sales AS DECIMAL(19,4)) AS corrected_net_sales,
           CAST(net_sales_delta AS DECIMAL(19,4)) AS net_sales_delta,
           exclusion_reason,
           CAST(NULL AS DATE) AS legacy_close_date
    FROM gb_micros_bridge
    UNION ALL
    SELECT source_system, store_id, business_date, check_id,
           CAST(legacy_net_sales AS DECIMAL(19,4)),
           CAST(corrected_net_sales AS DECIMAL(19,4)),
           CAST(net_sales_delta AS DECIMAL(19,4)),
           exclusion_reason, legacy_close_date
    FROM gb_aloha_bridge
""")
save(bridge, "comparison_bridge")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- comparison_summary: period-level waterfall ---
# App delta comes from daily_sales; check-level deltas come from the bridge.

waterfall = spark.sql("""
    SELECT exclusion_reason AS category,
           SUM(legacy_net_sales)    AS legacy_amount,
           SUM(corrected_net_sales) AS corrected_amount,
           SUM(net_sales_delta)     AS delta
    FROM gb_comparison_bridge
    GROUP BY exclusion_reason
    UNION ALL
    SELECT 'APP_REVENUE_REMOVED',
           SUM(legacy_app_net_sales), SUM(corrected_app_net_sales), SUM(net_sales_delta)
    FROM gb_app_bridge
""")
save(waterfall, "comparison_summary")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- comparison_daily: store/day level side-by-side ---

save(spark.sql(f"""
    SELECT l.store_id, l.business_date,
           COALESCE(l.net_sales, 0)        AS legacy_net_sales,
           COALESCE(c.net_sales, 0)        AS corrected_net_sales,
           COALESCE(c.net_sales, 0) - COALESCE(l.net_sales, 0) AS net_sales_delta,
           COALESCE(l.check_count, 0)      AS legacy_check_count,
           COALESCE(c.check_count, 0)      AS corrected_check_count
    FROM gold.legacy_daily_sales l
    FULL OUTER JOIN gold.corrected_daily_sales c
      ON l.store_id = c.store_id AND l.business_date = c.business_date
    WHERE COALESCE(l.business_date, c.business_date)
          BETWEEN DATE '{period_start}' AND DATE '{period_end}'
"""), "comparison_daily")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- comparison_invoices: invoice-level side-by-side ---

save(spark.sql("""
    SELECT COALESCE(l.store_id, c.store_id)             AS store_id,
           COALESCE(l.franchisee_id, c.franchisee_id)   AS franchisee_id,
           COALESCE(l.franchisee_name, c.franchisee_name) AS franchisee_name,
           COALESCE(l.net_sales, 0)      AS legacy_net_sales,
           COALESCE(c.net_sales, 0)      AS corrected_net_sales,
           COALESCE(c.net_sales, 0) - COALESCE(l.net_sales, 0) AS net_sales_delta,
           COALESCE(l.amount_due, 0)     AS legacy_amount_due,
           COALESCE(c.amount_due, 0)     AS corrected_amount_due,
           COALESCE(c.amount_due, 0) - COALESCE(l.amount_due, 0) AS amount_due_delta,
           CASE WHEN l.store_id IS NULL THEN 'CORRECTED_ONLY'
                WHEN c.store_id IS NULL THEN 'LEGACY_ONLY'
                ELSE 'BOTH' END AS invoice_status
    FROM gold.legacy_royalty_invoices l
    FULL OUTER JOIN gold.corrected_royalty_invoices c
      ON l.store_id = c.store_id AND l.period_start = c.period_start AND l.period_end = c.period_end
"""), "comparison_invoices")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Verification ---
# Period net-sales delta from bridge must match the documented difference between milestones.
EXPECTED_NET_SALES_LEGACY    = 299572.90
EXPECTED_NET_SALES_CORRECTED = 268893.08
EXPECTED_DELTA               = EXPECTED_NET_SALES_CORRECTED - EXPECTED_NET_SALES_LEGACY  # -30679.82

bridge_check_delta = spark.sql("SELECT SUM(net_sales_delta) AS d FROM gb_comparison_bridge").collect()[0][0] or 0
app_delta          = spark.sql("SELECT SUM(net_sales_delta) AS d FROM gb_app_bridge").collect()[0][0] or 0
total_bridge_delta = float(bridge_check_delta) + float(app_delta)

# Per-system diagnostics — compare bridge totals to Gold table totals to pinpoint any gap
for sys in ("MICROS", "ALOHA"):
    gl = spark.sql(f"SELECT SUM(net_sales) FROM gold.legacy_fact_checks WHERE source_system='{sys}'").collect()[0][0] or 0
    gc = spark.sql(f"SELECT SUM(net_sales) FROM gold.corrected_fact_checks WHERE source_system='{sys}'").collect()[0][0] or 0
    bl = spark.sql(f"SELECT SUM(legacy_net_sales) FROM gb_comparison_bridge WHERE source_system='{sys}'").collect()[0][0] or 0
    bc = spark.sql(f"SELECT SUM(corrected_net_sales) FROM gb_comparison_bridge WHERE source_system='{sys}'").collect()[0][0] or 0
    print(f"{sys}: gold_legacy={float(gl):,.2f}  bridge_legacy={float(bl):,.2f}  miss_legacy={float(gl)-float(bl):,.2f}")
    print(f"{sys}: gold_corrected={float(gc):,.2f}  bridge_corrected={float(bc):,.2f}  miss_corrected={float(gc)-float(bc):,.2f}")

print(f"\nBridge delta (checks): {float(bridge_check_delta):,.2f}")
print(f"Bridge delta (app):    {float(app_delta):,.2f}")
print(f"Bridge delta total:    {total_bridge_delta:,.2f}")
print(f"Expected delta:        {EXPECTED_DELTA:,.2f}")

tolerance = 0.02  # allow 2 cents rounding accumulated across checks
assert abs(total_bridge_delta - EXPECTED_DELTA) <= tolerance, \
    f"Bridge delta {total_bridge_delta:.2f} does not reconcile to expected {EXPECTED_DELTA:.2f}"

legacy_period_sales = spark.sql(
    "SELECT SUM(net_sales) FROM gold.legacy_daily_sales").collect()[0][0] or 0
corrected_period_sales = spark.sql(
    "SELECT SUM(net_sales) FROM gold.corrected_daily_sales").collect()[0][0] or 0
print(f"\nLegacy period net sales:    {float(legacy_period_sales):,.2f}")
print(f"Corrected period net sales: {float(corrected_period_sales):,.2f}")
print(f"Actual period delta:        {float(corrected_period_sales) - float(legacy_period_sales):,.2f}")

spark.table("gold.comparison_summary").orderBy("category").show(truncate=False)
spark.table("gold.comparison_invoices").orderBy("store_id").show(truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
