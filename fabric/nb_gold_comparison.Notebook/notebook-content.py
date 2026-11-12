# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "ea1119c4-4cf6-49f3-b025-6596594dd487",
# META       "default_lakehouse_name": "lh_polarslice",
# META       "default_lakehouse_workspace_id": "c2e20e29-e252-489b-bd2f-10fb423600eb",
# META       "known_lakehouses": [
# META         {
# META           "id": "ea1119c4-4cf6-49f3-b025-6596594dd487"
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
# Legacy: all void_flag='N' checks (includes gifts, void-matched originals, duplicates)
# Corrected: excludes gifts, excludes both sides of matched void pairs, keeps one per duplicate group

spark.sql(f"""
    SELECT store_id, business_date, check_id, net_sales AS legacy_net_sales
    FROM gold.legacy_fact_checks
    WHERE source_system = 'MICROS'
      AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").createOrReplaceTempView("gb_micros_legacy")

spark.sql(f"""
    SELECT store_id, business_date, check_id, net_sales AS corrected_net_sales
    FROM gold.corrected_fact_checks
    WHERE source_system = 'MICROS'
      AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").createOrReplaceTempView("gb_micros_corrected")

# Join silver to classify MICROS-legacy-only exclusion reasons
spark.sql(f"""
    SELECT l.store_id, l.business_date, l.check_id,
           COALESCE(l.legacy_net_sales, 0) AS legacy_net_sales,
           COALESCE(c.corrected_net_sales, 0) AS corrected_net_sales,
           COALESCE(c.corrected_net_sales, 0) - COALESCE(l.legacy_net_sales, 0) AS net_sales_delta,
           CASE
               WHEN c.check_id IS NOT NULL AND l.check_id IS NOT NULL THEN 'BOTH'
               WHEN c.check_id IS NULL AND s.is_gift_check THEN 'GIFT_EXCLUDED'
               WHEN c.check_id IS NULL AND s.is_void_reversal THEN 'VOID_REVERSAL_EXCLUDED'
               WHEN c.check_id IS NULL AND EXISTS (
                   SELECT 1 FROM gb_sm sv WHERE sv.store_id = l.store_id
                     AND sv.business_date = l.business_date
                     AND CAST(sv.check_no AS STRING) = l.check_id
                     AND sv.void_flag = 'V'
               ) THEN 'VOID_MATCHED_EXCLUDED'
               WHEN c.check_id IS NULL AND s.is_duplicate_check THEN 'DUPLICATE_EXCLUDED'
               WHEN c.check_id IS NULL THEN 'LEGACY_ONLY_OTHER'
               ELSE 'CORRECTED_ONLY'
           END AS exclusion_reason,
           'MICROS' AS source_system
    FROM gb_micros_legacy l
    FULL OUTER JOIN gb_micros_corrected c
      ON l.store_id = c.store_id AND l.business_date = c.business_date AND l.check_id = c.check_id
    LEFT JOIN gb_sm s
      ON s.store_id = COALESCE(l.store_id, c.store_id)
     AND s.business_date = COALESCE(l.business_date, c.business_date)
     AND CAST(s.check_no AS STRING) = COALESCE(l.check_id, c.check_id)
     AND s.void_flag = 'N'
""").createOrReplaceTempView("gb_micros_bridge")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# --- Aloha bridge ---
# Legacy uses to_date(close_ts) as business date; check_id = "YYYYMMDD-CHECKID"
# Corrected uses DOB as business date; check_id = numeric CHECKID string
# Join via Silver on (store_id, DOB, CHECKID) to reconcile the two date schemes

spark.sql(f"""
    SELECT l.store_id,
           s.business_date AS dob,
           CAST(s.check_id AS STRING) AS numeric_check_id,
           l.business_date AS legacy_close_date,
           s.business_date AS corrected_dob,
           l.net_sales AS legacy_net_sales,
           s.net_sales_excl_tax AS silver_net_sales_excl_tax,
           s.net_total_tax_incl AS silver_net_total_tax_incl
    FROM gold.legacy_fact_checks l
    JOIN gb_sa s
      ON s.store_id = l.store_id
     AND CAST(s.check_id AS STRING) = regexp_extract(l.check_id, '-([0-9]+)$', 1)
     AND s.business_date = to_date(regexp_extract(l.check_id, '^([0-9]{{8}})', 1), 'yyyyMMdd')
    WHERE l.source_system = 'ALOHA'
      AND l.business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").createOrReplaceTempView("gb_aloha_legacy_keyed")

spark.sql(f"""
    SELECT store_id, business_date AS dob, check_id AS numeric_check_id,
           net_sales AS corrected_net_sales
    FROM gold.corrected_fact_checks
    WHERE source_system = 'ALOHA'
      AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""").createOrReplaceTempView("gb_aloha_corrected")

# Full outer join on (store_id, DOB, numeric_check_id)
spark.sql("""
    SELECT COALESCE(l.store_id, c.store_id) AS store_id,
           COALESCE(l.dob, c.dob) AS business_date,
           COALESCE(l.numeric_check_id, c.numeric_check_id) AS check_id,
           COALESCE(l.legacy_net_sales, 0) AS legacy_net_sales,
           COALESCE(c.corrected_net_sales, 0) AS corrected_net_sales,
           COALESCE(c.corrected_net_sales, 0) - COALESCE(l.legacy_net_sales, 0) AS net_sales_delta,
           CASE
               WHEN l.numeric_check_id IS NOT NULL AND c.numeric_check_id IS NOT NULL
                    AND l.legacy_close_date <> l.corrected_dob THEN 'ALOHA_DATE_SHIFT'
               WHEN l.numeric_check_id IS NOT NULL AND c.numeric_check_id IS NOT NULL THEN 'BOTH'
               WHEN c.numeric_check_id IS NULL THEN 'ALOHA_DOB_OUTSIDE_PERIOD'
               ELSE 'ALOHA_DOB_IN_PERIOD_CLOSE_OUTSIDE'
           END AS exclusion_reason,
           l.legacy_close_date,
           l.silver_net_total_tax_incl,
           l.silver_net_sales_excl_tax,
           'ALOHA' AS source_system
    FROM gb_aloha_legacy_keyed l
    FULL OUTER JOIN gb_aloha_corrected c
      ON l.store_id = c.store_id AND l.dob = c.dob AND l.numeric_check_id = c.numeric_check_id
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
print(f"Bridge delta (checks): {bridge_check_delta:,.2f}")
print(f"Bridge delta (app):    {app_delta:,.2f}")
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
