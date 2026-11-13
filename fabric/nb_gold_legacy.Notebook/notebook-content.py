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

# # Gold: legacy SliceDW reproduction
# Mirrors `02_programmability.sql` and `03_reference_data.sql`. Known legacy defects are intentional.
# Outputs replace the selected period snapshot, not historical partitions. Run after Silver and `nb_gold_reference_data`.

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
from datetime import date
from pyspark.sql import functions as F

BATCH_ID = batch_id or str(uuid.uuid4())
start, end = date.fromisoformat(period_start), date.fromisoformat(period_end)
assert start <= end, "Period start must not exceed period end"
spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

def save(df, table, keys=(), money=()):
    for column in money:
        df = df.withColumn(column, F.col(column).cast("DECIMAL(19,4)"))
        assert df.filter(F.col(column).isNull()).count() == 0, f"{table}: invalid {column}"
    if keys:
        assert df.groupBy(*keys).count().filter("count > 1").count() == 0, \
            f"{table}: duplicate report keys"
    df = (df.withColumn("_gold_batch_id", F.lit(BATCH_ID))
          .withColumn("_rules_version", F.lit("slicedw-legacy-march-2026-v1")))
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"gold.{table}"))
    result = spark.table(f"gold.{table}")
    result.createOrReplaceTempView(f"gl_{table}")
    print(f"gold.{table}: {result.count()} rows")

inputs = {
    "mh": "silver.micros_checks", "md": "silver.micros_check_lines",
    "ac": "silver.aloha_checks", "ai": "silver.aloha_check_lines",
    "orders": "silver.online_orders", "stores": "silver.stores",
    "menu": "silver.menu", "recipes": "silver.recipes", "calendar": "silver.calendar",
    "items": "silver.as400_item_master", "shipments": "silver.as400_shipments",
    "counts": "silver.as400_stock_counts",
    "terms": "gold.reference_royalty_terms", "org": "gold.reference_org_units",
    "aloha_map": "gold.reference_legacy_aloha_map",
    "adjustments": "gold.reference_manual_adjustments",
}
manifest = []
silver_batches = set()
reference_batches = set()
for alias, table in inputs.items():
    df = spark.table(table)
    batch_column = "_silver_batch_id" if table.startswith("silver.") else "_gold_batch_id"
    batches = df.select(batch_column).distinct().collect()
    assert len(batches) == 1 and batches[0][0], f"{table}: expected one non-empty input batch"
    if table.startswith("silver."):
        silver_batches.add(batches[0][0])
    else:
        reference_batches.add(batches[0][0])
    manifest.append((table, batches[0][0], df.count(), period_start, period_end))
    df.createOrReplaceTempView(f"gl_{alias}")
assert len(silver_batches) == 1, \
    f"Silver inputs must come from one successful runner batch: {[(r[0], r[1]) for r in manifest if r[0].startswith('silver.')]}"
assert len(reference_batches) == 1, "Gold references must come from one successful reference batch"
calendar_dates = {r.business_date for r in spark.table("silver.calendar").collect()}
assert start in calendar_dates and end in calendar_dates, "Period boundaries must exist in Silver calendar"
save(spark.createDataFrame(manifest,
    "input_table STRING, input_batch_id STRING, row_count LONG, period_start STRING, period_end STRING"),
    "legacy_run_inputs", keys=("input_table",))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# SQL filters are deliberately legacy filters, not Silver's anomaly or matching flags.
fact_checks = spark.sql(f"""
    SELECT store_id, business_date, 'MICROS' AS source_system,
           CAST(check_no AS STRING) AS check_id, order_type, tender,
           subtotal AS gross, discount, tax, tip, subtotal - discount AS net_sales, online_ref,
           _source_file, _batch_id, _silver_batch_id
    FROM gl_mh WHERE business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
      AND void_flag = 'N'
    UNION ALL
    SELECT store_id, to_date(close_ts) AS business_date, 'ALOHA',
           concat(date_format(business_date, 'yyyyMMdd'), '-', CAST(check_id AS STRING)),
           ORDERMODE, PAYTYPE, gross_tax_incl, comp_tax_incl, tax, tip, net_total_tax_incl,
           CAST(NULL AS STRING), _source_file, _batch_id, _silver_batch_id
    FROM gl_ac WHERE to_date(close_ts) BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""")
save(fact_checks, "legacy_fact_checks", money=("gross", "discount", "tax", "tip", "net_sales"))

fact_lines = spark.sql(f"""
    SELECT d.store_id, d.business_date, 'MICROS' AS source_system,
           CAST(d.check_no AS STRING) AS check_id, m.sku,
           CAST(d.item_no AS STRING) AS source_item_code, d.qty, d.line_amount AS amount,
           d._source_file, d._batch_id, d._silver_batch_id
    FROM gl_md d LEFT JOIN gl_menu m ON m.micros_item_no = d.item_no
    WHERE d.business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
      AND d.line_type IN ('ITEM', 'GIFT')
    UNION ALL
    SELECT i.store_id, to_date(c.close_ts), 'ALOHA',
           concat(date_format(i.business_date, 'yyyyMMdd'), '-', CAST(i.check_id AS STRING)),
           m.sku, i.ITEMCODE, i.qty, i.amount_tax_incl,
           i._source_file, i._batch_id, i._silver_batch_id
    FROM gl_ai i JOIN gl_ac c
      ON c.store_id = i.store_id AND c.business_date = i.business_date AND c.check_id = i.check_id
    LEFT JOIN gl_aloha_map m ON m.aloha_item_code = i.ITEMCODE
    WHERE to_date(c.close_ts) BETWEEN DATE '{period_start}' AND DATE '{period_end}' AND i.TYPE = 'ITEM'
""")
save(fact_lines, "legacy_fact_check_lines", money=("amount",))

fact_online = spark.sql(f"""
    SELECT o.order_id, o.store_id, to_date(o.placed_local_ts) AS business_date,
           o.status, o.subtotal - o.discount AS net_sales, o.pos_check_no,
           f.check_id IS NOT NULL AS is_duplicate_of_pos, o._source_file, o._batch_id, o._silver_batch_id
    FROM gl_orders o
    LEFT JOIN (
        SELECT DISTINCT store_id, business_date, check_id FROM gl_legacy_fact_checks
        WHERE source_system = 'MICROS'
    ) f ON f.store_id = o.store_id AND f.business_date = to_date(o.placed_local_ts)
       AND f.check_id = CAST(o.pos_check_no AS STRING)
    WHERE to_date(o.placed_local_ts) BETWEEN DATE '{period_start}' AND DATE '{period_end}'
      AND o.status <> 'refunded'
""")
save(fact_online, "legacy_fact_online_orders", keys=("order_id",), money=("net_sales",))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

daily = spark.sql(f"""
    WITH tills AS (
        SELECT store_id, business_date, SUM(gross) AS gross_sales, SUM(discount) AS discounts,
               SUM(net_sales) AS net_sales_tills, SUM(tax) AS tax, COUNT(*) AS check_count,
               concat_ws(',', sort_array(collect_set(tender))) AS tender_list
        FROM gl_legacy_fact_checks GROUP BY store_id, business_date
    ), online AS (
        SELECT store_id, business_date, SUM(net_sales) AS online_only_sales
        FROM gl_legacy_fact_online_orders WHERE NOT is_duplicate_of_pos GROUP BY store_id, business_date
    ), voids AS (
        SELECT store_id, business_date, -SUM(subtotal) AS voids
        FROM gl_mh WHERE void_flag = 'V'
          AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
        GROUP BY store_id, business_date
    ), days AS (
        SELECT store_id, business_date FROM tills UNION SELECT store_id, business_date FROM online
    )
    SELECT d.store_id, d.business_date, COALESCE(t.gross_sales, 0) AS gross_sales,
           COALESCE(t.discounts, 0) AS discounts, COALESCE(v.voids, 0) AS voids,
           COALESCE(t.net_sales_tills, 0) AS net_sales_tills,
           COALESCE(o.online_only_sales, 0) AS online_only_sales,
           COALESCE(t.net_sales_tills, 0) + COALESCE(o.online_only_sales, 0) AS net_sales,
           COALESCE(t.tax, 0) AS tax, COALESCE(t.check_count, 0) AS check_count, t.tender_list
    FROM days d LEFT JOIN tills t ON t.store_id = d.store_id AND t.business_date = d.business_date
    LEFT JOIN online o ON o.store_id = d.store_id AND o.business_date = d.business_date
    LEFT JOIN voids v ON v.store_id = d.store_id AND v.business_date = d.business_date
""")
save(daily, "legacy_daily_sales", keys=("store_id", "business_date"),
     money=("gross_sales", "discounts", "voids", "net_sales_tills", "online_only_sales", "net_sales", "tax"))

promo = spark.sql(f"""
    SELECT store_id, business_date, promo_name, SUM(amount) AS discount_amount
    FROM (
        SELECT store_id, business_date,
               CASE item_no WHEN 9001 THEN '2FOR1TUE' WHEN 9002 THEN 'WELCOME10' ELSE 'STAFF50' END AS promo_name,
               -line_amount AS amount
        FROM gl_md WHERE line_type = 'DISC'
          AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
        UNION ALL
        SELECT store_id, to_date(order_ts),
               CASE ITEMCODE WHEN '2F1TUE' THEN '2FOR1TUE' ELSE 'STAFF50' END, -amount_tax_incl
        FROM gl_ai WHERE TYPE = 'COMP'
          AND to_date(order_ts) BETWEEN DATE '{period_start}' AND DATE '{period_end}'
    ) p GROUP BY store_id, business_date, promo_name
""")
save(promo, "legacy_promo_cost", keys=("store_id", "business_date", "promo_name"), money=("discount_amount",))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

save(spark.sql("""
    SELECT item_code, item_desc, pack_uom, base_uom, pack_qty, pack_cost FROM gl_items
"""), "legacy_dim_items", keys=("item_code",), money=("pack_cost",))
save(spark.sql("""
    SELECT store_id, ship_date, item_code, quantity AS qty_cases,
           CAST(substring(ext_cost_raw, 1, 9) AS DECIMAL(11,0)) / 100 AS ext_cost,
           regexp_extract(_source_file, '([^/]+)$', 1) AS source_file
    FROM gl_shipments
"""), "legacy_shipments", money=("ext_cost",))
save(spark.sql("""
    SELECT store_id, count_date, count_type, item_code, quantity_on_hand AS qty FROM gl_counts
"""), "legacy_stock_counts", keys=("store_id", "count_date", "count_type", "item_code"))

terms = {r.term_code: r.term_value for r in spark.table("gold.reference_royalty_terms").collect()}
assert {"ROYALTY_RATE", "AD_FUND_RATE", "NEW_STORE_HOLIDAY_MONTHS"} <= terms.keys(), \
    "Missing royalty terms"
royalty = spark.sql(f"""
    WITH sales AS (
        SELECT store_id, SUM(net_sales) AS net_sales FROM gl_legacy_daily_sales GROUP BY store_id
    ), adjustments AS (
        SELECT store_id, SUM(amount) AS adjustments FROM gl_adjustments
        WHERE business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}' GROUP BY store_id
    ), invoices AS (
        SELECT s.franchisee_id, s.franchisee_name, s.store_id,
               DATE '{period_start}' AS period_start, DATE '{period_end}' AS period_end, ns.net_sales,
               round(CAST(ns.net_sales AS DECIMAL(19,4))
                     * CAST('{terms["ROYALTY_RATE"]}' AS DECIMAL(9,4)), 2) AS royalty,
               round(CAST(ns.net_sales AS DECIMAL(19,4))
                     * CAST('{terms["AD_FUND_RATE"]}' AS DECIMAL(9,4)), 2) AS ad_fund,
               COALESCE(a.adjustments, 0) AS adjustments
        FROM gl_stores s JOIN sales ns ON ns.store_id = s.store_id
        LEFT JOIN adjustments a ON a.store_id = s.store_id
        WHERE s.ownership = 'FRANCHISE' AND s.open_date <= add_months(DATE '{period_end}', -3)
    )
    SELECT *, royalty + ad_fund + adjustments AS amount_due FROM invoices
""")
save(royalty, "legacy_royalty_invoices", keys=("store_id", "period_start", "period_end"),
     money=("net_sales", "royalty", "ad_fund", "adjustments", "amount_due"))

food = spark.sql(f"""
    WITH theo AS (
        SELECT l.store_id, r.ingredient_item_code AS item_code,
               SUM(l.qty * r.qty_per_unit) AS theoretical
        FROM gl_legacy_fact_check_lines l JOIN gl_recipes r ON r.sku = l.sku
        GROUP BY l.store_id, r.ingredient_item_code
    ), recv AS (
        SELECT sh.store_id, sh.item_code, SUM(sh.qty_cases * i.pack_qty) AS received
        FROM gl_legacy_shipments sh JOIN gl_legacy_dim_items i ON i.item_code = sh.item_code
        WHERE sh.ship_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
        GROUP BY sh.store_id, sh.item_code
    ), usage AS (
        SELECT o.store_id, DATE '{period_start}' AS period_start, DATE '{period_end}' AS period_end,
               o.item_code, o.qty AS opening_qty, COALESCE(rc.received, 0) AS received_qty,
               c.qty AS closing_qty, o.qty + COALESCE(rc.received, 0) - c.qty AS actual_usage,
               COALESCE(t.theoretical, 0) AS theoretical_usage, i.pack_cost, i.pack_qty
        FROM gl_legacy_stock_counts o JOIN gl_legacy_stock_counts c
          ON c.store_id = o.store_id AND c.item_code = o.item_code
         AND c.count_type = 'C' AND c.count_date = DATE '{period_end}'
        JOIN gl_legacy_dim_items i ON i.item_code = o.item_code
        LEFT JOIN recv rc ON rc.store_id = o.store_id AND rc.item_code = o.item_code
        LEFT JOIN theo t ON t.store_id = o.store_id AND t.item_code = o.item_code
        WHERE o.count_type = 'O' AND o.count_date = DATE '{period_start}'
    ), variance AS (
        SELECT *, actual_usage - theoretical_usage AS variance FROM usage
    )
    SELECT store_id, period_start, period_end, item_code,
           CAST(opening_qty AS DECIMAL(12,3)) AS opening_qty,
           CAST(received_qty AS DECIMAL(12,3)) AS received_qty,
           CAST(closing_qty AS DECIMAL(12,3)) AS closing_qty,
           CAST(actual_usage AS DECIMAL(12,3)) AS actual_usage,
           CAST(theoretical_usage AS DECIMAL(12,3)) AS theoretical_usage,
           CAST(variance AS DECIMAL(12,3)) AS variance,
           CASE WHEN theoretical_usage = 0 THEN CAST(NULL AS DECIMAL(9,1))
                ELSE CAST(round(variance / theoretical_usage * 100, 1) AS DECIMAL(9,1)) END AS variance_pct,
           round(variance * CAST(pack_cost AS DECIMAL(19,4)) / pack_qty, 2) AS variance_cost
    FROM variance
""")
save(food, "legacy_food_cost_variance", keys=("store_id", "period_start", "period_end", "item_code"),
     money=("variance_cost",))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Expand the SQL recursive CTE as a validated ancestor closure, including each store's self row.
org_rows = spark.table("gold.reference_org_units").collect()
org = {r.unit_id: r for r in org_rows}
assert len(org) == len(org_rows), "Duplicate organization unit IDs"
closure = []
for row in org_rows:
    if row.store_id is None:
        continue
    unit, visited = row.unit_id, set()
    while unit is not None:
        assert unit in org, f"Organization parent {unit} does not exist"
        assert unit not in visited, f"Cycle in organization hierarchy at {unit}"
        assert len(visited) <= 10, "Organization recursion exceeds SliceDW MAXRECURSION 10"
        visited.add(unit)
        closure.append((unit, row.store_id))
        unit = org[unit].parent_unit_id
spark.createDataFrame(closure, "unit_id INT, store_id INT").createOrReplaceTempView("gl_closure")
save(spark.sql("""
    SELECT u.unit_id, u.unit_name, u.unit_type, f.business_date, SUM(f.net_sales) AS net_sales
    FROM gl_closure t JOIN gl_org u ON u.unit_id = t.unit_id
    JOIN gl_legacy_daily_sales f ON f.store_id = t.store_id
    GROUP BY u.unit_id, u.unit_name, u.unit_type, f.business_date
"""), "legacy_region_daily_sales", keys=("unit_id", "business_date"), money=("net_sales",))
save(spark.sql("""
    SELECT franchisee_id, franchisee_name, period_start, period_end, COUNT(*) AS stores,
           SUM(net_sales) AS net_sales, SUM(royalty) AS royalty, SUM(ad_fund) AS ad_fund,
           SUM(adjustments) AS adjustments, SUM(amount_due) AS amount_due
    FROM gl_legacy_royalty_invoices
    GROUP BY franchisee_id, franchisee_name, period_start, period_end
"""), "legacy_franchisee_invoices", keys=("franchisee_id", "period_start", "period_end"),
     money=("net_sales", "royalty", "ad_fund", "adjustments", "amount_due"))
save(spark.sql("""
    SELECT store_id, business_date, source_system, SUM(net_sales) AS net_sales,
           SUM(tax) AS tax, COUNT(*) AS check_count
    FROM gl_legacy_fact_checks GROUP BY store_id, business_date, source_system
"""), "legacy_store_day_sales", keys=("store_id", "business_date", "source_system"), money=("net_sales", "tax"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

if (period_start, period_end) == ("2026-03-09", "2026-03-13"):
    expected_counts = {
        "legacy_fact_checks": 9269, "legacy_fact_check_lines": 25681,
        "legacy_fact_online_orders": 2296, "legacy_daily_sales": 50,
        "legacy_promo_cost": 72, "legacy_dim_items": 19,
        "legacy_shipments": 564, "legacy_stock_counts": 380,
        "legacy_royalty_invoices": 9, "legacy_food_cost_variance": 190,
        "legacy_region_daily_sales": 85, "legacy_franchisee_invoices": 7,
        "legacy_store_day_sales": 50,
    }
    for table, expected in expected_counts.items():
        actual = spark.table(f"gold.{table}").count()
        assert actual == expected, f"{table}: expected {expected} source-pack rows, found {actual}"
assert spark.sql("""
    SELECT * FROM gl_legacy_daily_sales
    WHERE net_sales <> net_sales_tills + online_only_sales
""").count() == 0, "Legacy daily sales do not balance"
assert spark.sql("""
    SELECT * FROM gl_legacy_royalty_invoices
    WHERE amount_due <> royalty + ad_fund + adjustments
""").count() == 0, "Legacy invoice amounts do not balance"
assert spark.sql("""
    SELECT f.business_date FROM gl_legacy_region_daily_sales f
    JOIN (SELECT business_date, SUM(net_sales) AS net_sales
          FROM gl_legacy_daily_sales GROUP BY business_date) d ON d.business_date = f.business_date
    WHERE f.unit_type = 'COMPANY' AND f.net_sales <> d.net_sales
""").count() == 0, "Company rollup does not equal store-day sales"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
