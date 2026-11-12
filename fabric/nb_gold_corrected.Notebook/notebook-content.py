# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "f8d5782d-d817-44fe-a071-613af0122930",
# META       "default_lakehouse_name": "lh_polarslice",
# META       "default_lakehouse_workspace_id": "",
# META       "known_lakehouses": [
# META         {
# META           "id": "f8d5782d-d817-44fe-a071-613af0122930"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Gold: corrected business results
# POS is the sales system of record. Online links provide attribution only; ambiguous links remain unresolved.
# Requires one successful Silver batch and the versioned Gold references. Never writes legacy or reference tables.

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
from pyspark.sql import Window, functions as F

BATCH_ID = batch_id or str(uuid.uuid4())
RULES_VERSION = "polarslice-corrected-v1"
start, end = date.fromisoformat(period_start), date.fromisoformat(period_end)
assert start <= end, "Period start must not exceed period end"
spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

def save(df, table, keys=(), money=()):
    assert table.startswith("corrected_"), f"Refusing to overwrite non-corrected output: {table}"
    for column in money:
        df = df.withColumn(column, F.col(column).cast("DECIMAL(19,4)"))
        assert df.filter(F.col(column).isNull()).count() == 0, f"{table}: invalid {column}"
    if keys:
        assert df.filter(F.expr(" OR ".join(f"`{key}` IS NULL" for key in keys))).count() == 0, \
            f"{table}: null report keys"
        assert df.groupBy(*keys).count().filter("count > 1").count() == 0, \
            f"{table}: duplicate report keys"
    df = (df.withColumn("_gold_batch_id", F.lit(BATCH_ID))
          .withColumn("_rules_version", F.lit(RULES_VERSION)))
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"gold.{table}"))
    result = spark.table(f"gold.{table}")
    result.createOrReplaceTempView(f"gc_{table}")
    print(f"gold.{table}: {result.count()} rows")

inputs = {
    "mh": "silver.micros_checks", "md": "silver.micros_check_lines",
    "ac": "silver.aloha_checks", "ai": "silver.aloha_check_lines",
    "orders": "silver.online_orders", "stores": "silver.stores",
    "menu": "silver.menu", "recipes": "silver.recipes", "calendar": "silver.calendar",
    "items": "silver.as400_item_master", "shipments": "silver.as400_shipments",
    "counts": "silver.as400_stock_counts",
    "terms": "gold.reference_royalty_terms", "org": "gold.reference_org_units",
    "adjustments": "gold.reference_manual_adjustments",
}
manifest = []
for alias, table in inputs.items():
    df = spark.table(table)
    batch_column = "_silver_batch_id" if table.startswith("silver.") else "_gold_batch_id"
    batches = [r[0] for r in df.select(batch_column).distinct().collect()]
    assert len(batches) == 1 and batches[0], f"{table}: expected one non-empty input batch: {batches}"
    manifest.append((table, batches[0], df.count(), period_start, period_end))
    df.createOrReplaceTempView(f"gc_{alias}")
for prefix in ("silver.", "gold."):
    batches = {r[1] for r in manifest if r[0].startswith(prefix)}
    assert len(batches) == 1, f"Mixed {prefix} input batches: {manifest}"
calendar_dates = {r.business_date for r in spark.table("silver.calendar").collect()}
assert start in calendar_dates and end in calendar_dates, "Period boundaries must exist in Silver calendar"
assert spark.sql("SELECT * FROM gc_items WHERE pack_qty IS NULL OR pack_qty <= 0").count() == 0, \
    "Invalid ingredient pack quantity"
assert spark.sql("""
    SELECT sh.* FROM gc_shipments sh LEFT JOIN gc_items i ON i.item_code = sh.item_code
    WHERE i.item_code IS NULL OR sh.quantity_base_units IS NULL OR sh.ext_cost IS NULL
       OR sh.base_uom <> i.base_uom
""").count() == 0, "Invalid shipment quantity, cost, or unit"
assert spark.sql("""
    SELECT r.* FROM gc_recipes r LEFT JOIN gc_items i ON i.item_code = r.ingredient_item_code
    WHERE i.item_code IS NULL OR r.base_uom <> i.base_uom OR r.qty_per_unit IS NULL
""").count() == 0, "Invalid recipe ingredient or unit"
for kind, boundary in (("O", period_start), ("C", period_end)):
    snapshot = spark.table("silver.as400_stock_counts").filter(
        (F.col("count_type") == kind) & (F.col("count_date") == F.lit(boundary)))
    assert snapshot.groupBy("store_id", "item_code").count().filter("count > 1").count() == 0, \
        f"Duplicate {kind} stock counts at {boundary}"
    snapshot.createOrReplaceTempView("gc_stock_boundary")
    assert spark.sql("""
        SELECT s.store_id, i.item_code FROM gc_stores s CROSS JOIN gc_items i
        LEFT ANTI JOIN gc_stock_boundary c ON c.store_id = s.store_id AND c.item_code = i.item_code
    """).count() == 0, f"Missing {kind} stock counts at {boundary}; corrected food cost requires complete boundaries"
    assert spark.sql("""
        SELECT c.* FROM gc_stock_boundary c JOIN gc_items i ON i.item_code = c.item_code
        WHERE c.quantity_on_hand IS NULL OR c.base_uom <> i.base_uom
    """).count() == 0, f"Invalid {kind} stock counts at {boundary}"

def canonical(alias, keys):
    df = spark.sql(f"SELECT * FROM gc_{alias}")
    business = [c for c in df.columns if not c.startswith("_") and not c.startswith("is_duplicate")]
    assert df.select(*business).distinct().groupBy(*keys).count().filter("count > 1").count() == 0, \
        f"{alias}: conflicting versions for {keys}; cannot select a winner"
    assert df.filter(F.expr(" OR ".join(f"`{key}` IS NULL" for key in keys))).count() == 0, \
        f"{alias}: null source keys"
    df = (df.withColumn("_poll_rank", F.row_number().over(
        Window.partitionBy(*keys).orderBy("_source_file", "_batch_id")))
        .filter("_poll_rank = 1").drop("_poll_rank"))
    df.createOrReplaceTempView(f"gc_{alias}_unique")

canonical("mh", ("store_id", "business_date", "check_no", "void_flag"))
canonical("md", ("store_id", "business_date", "check_no", "line_no", "line_type"))
canonical("ac", ("store_id", "business_date", "check_id"))
canonical("ai", ("store_id", "business_date", "check_id", "entry_id"))
assert spark.sql("SELECT * FROM gc_mh_unique WHERE void_flag NOT IN ('N', 'V') OR void_flag IS NULL").count() == 0, \
    "Unknown MICROS void flag"
assert spark.sql("""
    SELECT v.* FROM gc_mh_unique v LEFT JOIN gc_mh_unique h
      ON h.store_id = v.store_id AND h.business_date = v.business_date
     AND h.check_no = v.check_no AND h.void_flag = 'N'
    WHERE v.void_flag = 'V' AND (h.check_no IS NULL OR
        v.subtotal <> -h.subtotal OR v.discount <> -h.discount OR v.tax <> -h.tax
        OR v.tip <> -h.tip OR v.total <> -h.total)
""").count() == 0, "MICROS void is not an exact whole-check reversal"

spark.sql("""
    SELECT h.* FROM gc_mh_unique h LEFT ANTI JOIN gc_mh_unique v
      ON v.store_id = h.store_id AND v.business_date = h.business_date
     AND v.check_no = h.check_no AND v.void_flag = 'V'
    WHERE h.void_flag = 'N' AND NOT h.is_gift_check
""").createOrReplaceTempView("gc_micros_sales")
assert spark.sql("""
    SELECT d.* FROM gc_md_unique d LEFT JOIN gc_mh_unique h
      ON h.store_id = d.store_id AND h.business_date = d.business_date
     AND h.check_no = d.check_no AND h.void_flag = 'N'
    WHERE h.check_no IS NULL
""").count() == 0, "Orphan MICROS lines"
assert spark.sql("""
    SELECT i.* FROM gc_ai_unique i LEFT JOIN gc_ac_unique c
      ON c.store_id = i.store_id AND c.business_date = i.business_date AND c.check_id = i.check_id
    WHERE c.check_id IS NULL
""").count() == 0, "Orphan Aloha lines"
assert spark.sql("""
    SELECT * FROM gc_md_unique WHERE line_type = 'ITEM' AND sku IS NULL
    UNION ALL SELECT * FROM gc_md_unique WHERE line_type NOT IN ('ITEM', 'DISC', 'GIFT', 'VOID')
""").count() == 0, "Invalid MICROS item mapping or line type"
assert spark.sql("SELECT * FROM gc_ai_unique WHERE (TYPE = 'ITEM' AND sku IS NULL) OR TYPE NOT IN ('ITEM', 'COMP')").count() == 0, \
    "Invalid Aloha item mapping or line type"
assert spark.sql("""
    SELECT * FROM gc_md_unique WHERE line_type = 'DISC' AND item_no NOT IN (9001, 9002, 9003)
""").count() == 0, "Unknown MICROS promotion"
assert spark.sql("""
    SELECT * FROM gc_ai_unique WHERE TYPE = 'COMP' AND ITEMCODE NOT IN ('2F1TUE', 'EMP50')
""").count() == 0, "Unknown Aloha promotion"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

save(spark.createDataFrame(manifest,
    "input_table STRING, input_batch_id STRING, row_count LONG, period_start STRING, period_end STRING"),
    "corrected_run_inputs", keys=("input_table",))

promotions = spark.sql(f"""
    SELECT d.store_id, d.business_date, 'MICROS' AS source_system,
           CAST(d.check_no AS STRING) AS check_id,
           CASE d.item_no WHEN 9001 THEN '2FOR1TUE' WHEN 9002 THEN 'WELCOME10' WHEN 9003 THEN 'STAFF50' END AS promo_name,
           -d.line_amount AS discount_amount
    FROM gc_md_unique d JOIN gc_micros_sales h
      ON h.store_id = d.store_id AND h.business_date = d.business_date AND h.check_no = d.check_no
    WHERE d.line_type = 'DISC' AND d.business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
    UNION ALL
    SELECT store_id, business_date, 'ALOHA', CAST(check_id AS STRING),
           CASE ITEMCODE WHEN '2F1TUE' THEN '2FOR1TUE' WHEN 'EMP50' THEN 'STAFF50' END,
           round(-amount_tax_incl / CAST(1.13 AS DECIMAL(4,2)), 2)
    FROM gc_ai_unique
    WHERE TYPE = 'COMP' AND business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""")
promotions.createOrReplaceTempView("gc_promotions")
save(spark.sql("""
    SELECT store_id, business_date, promo_name, SUM(discount_amount) AS discount_amount
    FROM gc_promotions GROUP BY store_id, business_date, promo_name
"""), "corrected_promo_cost", keys=("store_id", "business_date", "promo_name"), money=("discount_amount",))

facts = spark.sql(f"""
    SELECT h.store_id, h.business_date, 'MICROS' AS source_system,
           CAST(h.check_no AS STRING) AS check_id,
           concat_ws('|', h.store_id, date_format(h.business_date, 'yyyyMMdd'), h.check_no) AS check_key,
           h.order_type, h.tender, h.subtotal AS gross, h.discount,
           h.subtotal - h.discount AS net_sales, h.tax, h.tip, h.total,
           h.online_ref, h.tender = 'WEB' AS is_online,
           h._source_file, h._batch_id, h._silver_batch_id
    FROM gc_micros_sales h
    WHERE h.business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
    UNION ALL
    SELECT c.store_id, c.business_date, 'ALOHA', CAST(c.check_id AS STRING), c.check_key,
           c.ORDERMODE, c.PAYTYPE,
           c.net_sales_excl_tax + COALESCE(p.discount_amount, 0), COALESCE(p.discount_amount, 0),
           c.net_sales_excl_tax, c.tax, c.tip, c.total, CAST(NULL AS STRING), c.PAYTYPE = 'WEB',
           c._source_file, c._batch_id, c._silver_batch_id
    FROM gc_ac_unique c LEFT JOIN (
        SELECT store_id, business_date, check_id, SUM(discount_amount) AS discount_amount
        FROM gc_promotions WHERE source_system = 'ALOHA' GROUP BY store_id, business_date, check_id
    ) p ON p.store_id = c.store_id AND p.business_date = c.business_date AND p.check_id = CAST(c.check_id AS STRING)
    WHERE c.business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
""")
save(facts, "corrected_fact_checks", keys=("source_system", "check_key"),
     money=("gross", "discount", "net_sales", "tax", "tip", "total"))
save(spark.sql("""
    SELECT d.store_id, d.business_date, f.source_system, f.check_key, d.line_no,
           d.sku, CAST(d.item_no AS STRING) AS source_item_code, d.qty,
           d._source_file, d._batch_id, d._silver_batch_id
    FROM gc_md_unique d JOIN gc_corrected_fact_checks f
      ON f.source_system = 'MICROS' AND f.store_id = d.store_id
     AND f.business_date = d.business_date AND f.check_id = CAST(d.check_no AS STRING)
    WHERE d.line_type = 'ITEM'
    UNION ALL
    SELECT i.store_id, i.business_date, f.source_system, f.check_key, i.entry_id,
           i.sku, i.ITEMCODE, i.qty, i._source_file, i._batch_id, i._silver_batch_id
    FROM gc_ai_unique i JOIN gc_corrected_fact_checks f
      ON f.source_system = 'ALOHA' AND f.store_id = i.store_id
     AND f.business_date = i.business_date AND f.check_id = CAST(i.check_id AS STRING)
    WHERE i.TYPE = 'ITEM'
"""), "corrected_fact_check_lines", keys=("source_system", "check_key", "line_no"))

save(spark.sql(f"""
    SELECT o.order_id, o.store_id, o.business_date, o.status, o.pos_match_status,
           o.pos_match_system, o.pos_match_check_key, o.pos_match_candidate_count,
           o.pos_match_best_tie_count, o.pos_match_time_delta_seconds,
           CASE WHEN NOT o.is_completed THEN 'CANCELLED'
                WHEN o.pos_match_status IN ('AMBIGUOUS_MICROS', 'AMBIGUOUS_ALOHA') THEN o.pos_match_status
                WHEN f.check_key IS NOT NULL THEN o.pos_match_status
                ELSE 'UNRESOLVED_POS_LINK' END AS attribution_status,
           f.check_key AS attributed_check_key, f.net_sales AS attributed_net_sales,
           CAST(0 AS DECIMAL(19,4)) AS incremental_net_sales,
           o._source_file, o._batch_id, o._silver_batch_id
    FROM gc_orders o LEFT JOIN gc_corrected_fact_checks f
      ON o.is_completed AND o.pos_match_status IN ('MATCHED_MICROS', 'MATCHED_ALOHA')
     AND f.source_system = o.pos_match_system AND f.check_key = o.pos_match_check_key
    WHERE o.business_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
"""), "corrected_online_attribution", keys=("order_id",), money=("incremental_net_sales",))
assert spark.sql("""
    SELECT attributed_check_key FROM gc_corrected_online_attribution
    WHERE attributed_check_key IS NOT NULL
    GROUP BY pos_match_system, attributed_check_key HAVING COUNT(*) > 1
""").count() == 0, "Multiple app orders claim the same corrected POS check"

save(spark.sql("""
    SELECT store_id, business_date, SUM(gross) AS gross_sales, SUM(discount) AS discounts,
           SUM(net_sales) AS net_sales, SUM(tax) AS tax, SUM(tip) AS tips,
           SUM(CASE WHEN is_online THEN net_sales ELSE 0 END) AS online_pos_net_sales,
           COUNT(*) AS check_count, concat_ws(',', sort_array(collect_set(tender))) AS tender_list
    FROM gc_corrected_fact_checks GROUP BY store_id, business_date
"""), "corrected_daily_sales", keys=("store_id", "business_date"),
     money=("gross_sales", "discounts", "net_sales", "tax", "tips", "online_pos_net_sales"))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

adjustment_window = Window.partitionBy(
    "store_id", "business_date", "adj_type", "amount", "note").orderBy("keyed_at", "adjustment_id")
adjustments = (spark.table("gold.reference_manual_adjustments")
    .withColumn("duplicate_rank", F.row_number().over(adjustment_window))
    .withColumn("is_included", F.col("duplicate_rank") == 1)
    .withColumn("decision", F.when(F.col("is_included"), "INCLUDED").otherwise("DUPLICATE_CREDIT"))
    .filter(F.col("business_date").between(period_start, period_end)))
save(adjustments, "corrected_adjustment_decisions", keys=("adjustment_id",), money=("amount",))

term_rows = spark.table("gold.reference_royalty_terms").collect()
terms = {r.term_code: r.term_value for r in term_rows}
assert len(terms) == len(term_rows), "Duplicate royalty terms"
assert {"ROYALTY_RATE", "AD_FUND_RATE", "NEW_STORE_HOLIDAY_MONTHS"} <= terms.keys(), "Missing royalty terms"
months = terms["NEW_STORE_HOLIDAY_MONTHS"]
assert months is not None and months == int(months) and months >= 0, "Invalid royalty holiday months"
assert all(terms[k] is not None and 0 <= terms[k] <= 1 for k in ("ROYALTY_RATE", "AD_FUND_RATE")), \
    "Invalid royalty rates"
save(spark.sql(f"""
    WITH sales AS (
        SELECT store_id, SUM(net_sales) AS net_sales FROM gc_corrected_daily_sales GROUP BY store_id
    ), adjustments AS (
        SELECT store_id, SUM(amount) AS adjustments FROM gc_corrected_adjustment_decisions
        WHERE is_included GROUP BY store_id
    ), invoices AS (
        SELECT s.franchisee_id, s.franchisee_name, s.store_id,
               DATE '{period_start}' AS period_start, DATE '{period_end}' AS period_end, ns.net_sales,
               round(ns.net_sales * CAST('{terms["ROYALTY_RATE"]}' AS DECIMAL(9,4)), 2) AS royalty,
               round(ns.net_sales * CAST('{terms["AD_FUND_RATE"]}' AS DECIMAL(9,4)), 2) AS ad_fund,
               COALESCE(a.adjustments, 0) AS adjustments
        FROM gc_stores s JOIN sales ns ON ns.store_id = s.store_id
        LEFT JOIN adjustments a ON a.store_id = s.store_id
        WHERE s.ownership = 'FRANCHISE' AND add_months(s.open_date, {int(months)}) <= DATE '{period_end}'
    )
    SELECT *, royalty + ad_fund + adjustments AS amount_due FROM invoices
"""), "corrected_royalty_invoices", keys=("store_id", "period_start", "period_end"),
     money=("net_sales", "royalty", "ad_fund", "adjustments", "amount_due"))

save(spark.sql(f"""
    WITH theo AS (
        SELECT l.store_id, r.ingredient_item_code AS item_code, SUM(l.qty * r.qty_per_unit) AS theoretical
        FROM gc_corrected_fact_check_lines l JOIN gc_recipes r ON r.sku = l.sku
        GROUP BY l.store_id, r.ingredient_item_code
    ), receipts AS (
        SELECT store_id, item_code, SUM(quantity_base_units) AS received
        FROM gc_shipments WHERE ship_date BETWEEN DATE '{period_start}' AND DATE '{period_end}'
        GROUP BY store_id, item_code
    ), usage AS (
        SELECT o.store_id, DATE '{period_start}' AS period_start, DATE '{period_end}' AS period_end,
               o.item_code, i.base_uom, o.quantity_on_hand AS opening_qty,
               COALESCE(rc.received, 0) AS received_qty, c.quantity_on_hand AS closing_qty,
               o.quantity_on_hand + COALESCE(rc.received, 0) - c.quantity_on_hand AS actual_usage,
               COALESCE(t.theoretical, 0) AS theoretical_usage, i.pack_cost, i.pack_qty
        FROM gc_counts o JOIN gc_counts c ON c.store_id = o.store_id AND c.item_code = o.item_code
         AND c.count_type = 'C' AND c.count_date = DATE '{period_end}'
        JOIN gc_items i ON i.item_code = o.item_code
        LEFT JOIN receipts rc ON rc.store_id = o.store_id AND rc.item_code = o.item_code
        LEFT JOIN theo t ON t.store_id = o.store_id AND t.item_code = o.item_code
        WHERE o.count_type = 'O' AND o.count_date = DATE '{period_start}'
    ), variance AS (
        SELECT *, actual_usage - theoretical_usage AS variance FROM usage
    )
    SELECT store_id, period_start, period_end, item_code, base_uom,
           CAST(opening_qty AS DECIMAL(18,3)) AS opening_qty,
           CAST(received_qty AS DECIMAL(18,3)) AS received_qty,
           CAST(closing_qty AS DECIMAL(18,3)) AS closing_qty,
           CAST(actual_usage AS DECIMAL(18,3)) AS actual_usage,
           CAST(theoretical_usage AS DECIMAL(18,3)) AS theoretical_usage,
           CAST(variance AS DECIMAL(18,3)) AS variance,
           CASE WHEN theoretical_usage = 0 THEN CAST(NULL AS DECIMAL(12,1))
                ELSE CAST(round(CAST(variance AS DECIMAL(19,6)) /
                     CAST(theoretical_usage AS DECIMAL(19,6)) * 100, 1) AS DECIMAL(12,1)) END AS variance_pct,
           round(variance * CAST(pack_cost AS DECIMAL(19,4)) / pack_qty, 2) AS variance_cost
    FROM variance
"""), "corrected_food_cost_variance", keys=("store_id", "period_start", "period_end", "item_code"),
     money=("variance_cost",))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

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
        visited.add(unit)
        closure.append((unit, row.store_id))
        unit = org[unit].parent_unit_id
assert {store for _, store in closure} == {r.store_id for r in spark.table("silver.stores").collect()}, \
    "Organization hierarchy does not cover the Silver stores"
assert len(closure) == len(set(closure)), "Multiple organization paths for a store"
spark.createDataFrame(closure, "unit_id INT, store_id INT").createOrReplaceTempView("gc_closure")
save(spark.sql("""
    SELECT u.unit_id, u.unit_name, u.unit_type, f.business_date, SUM(f.net_sales) AS net_sales
    FROM gc_closure t JOIN gc_org u ON u.unit_id = t.unit_id
    JOIN gc_corrected_daily_sales f ON f.store_id = t.store_id
    GROUP BY u.unit_id, u.unit_name, u.unit_type, f.business_date
"""), "corrected_region_daily_sales", keys=("unit_id", "business_date"), money=("net_sales",))
save(spark.sql("""
    SELECT franchisee_id, franchisee_name, period_start, period_end, COUNT(*) AS stores,
           SUM(net_sales) AS net_sales, SUM(royalty) AS royalty, SUM(ad_fund) AS ad_fund,
           SUM(adjustments) AS adjustments, SUM(amount_due) AS amount_due
    FROM gc_corrected_royalty_invoices
    GROUP BY franchisee_id, franchisee_name, period_start, period_end
"""), "corrected_franchisee_invoices", keys=("franchisee_id", "period_start", "period_end"),
     money=("net_sales", "royalty", "ad_fund", "adjustments", "amount_due"))

assert spark.sql("""
    SELECT * FROM gc_corrected_fact_checks
    WHERE gross - discount <> net_sales OR net_sales + tax + tip <> total
""").count() == 0, "Corrected check amounts do not balance"
assert spark.sql("""
    SELECT d.* FROM gc_corrected_daily_sales d LEFT JOIN (
        SELECT store_id, business_date, SUM(discount_amount) AS discounts
        FROM gc_corrected_promo_cost GROUP BY store_id, business_date
    ) p ON p.store_id = d.store_id AND p.business_date = d.business_date
    WHERE d.discounts <> COALESCE(p.discounts, 0) OR d.gross_sales - d.discounts <> d.net_sales
""").count() == 0, "Corrected daily discounts do not reconcile to promotions"
assert spark.sql("""
    SELECT * FROM gc_corrected_royalty_invoices WHERE amount_due <> royalty + ad_fund + adjustments
""").count() == 0, "Corrected invoices do not balance"
assert spark.sql("""
    SELECT f.business_date FROM gc_corrected_region_daily_sales f
    JOIN (SELECT business_date, SUM(net_sales) AS net_sales FROM gc_corrected_daily_sales
          GROUP BY business_date) d ON d.business_date = f.business_date
    WHERE f.unit_type = 'COMPANY' AND f.net_sales <> d.net_sales
""").count() == 0, "Corrected company rollup does not equal daily sales"
assert spark.sql("""
    SELECT * FROM gc_corrected_food_cost_variance
    WHERE variance <> actual_usage - theoretical_usage
       OR actual_usage <> opening_qty + received_qty - closing_qty
       OR (theoretical_usage <> 0 AND variance_pct IS NULL)
""").count() == 0, "Corrected food-cost quantities or percentages do not balance"
if (period_start, period_end) == ("2026-03-09", "2026-03-13"):
    expected_counts = {
        "corrected_run_inputs": 15, "corrected_promo_cost": 69,
        "corrected_fact_checks": 9231, "corrected_fact_check_lines": 25664,
        "corrected_online_attribution": 2302, "corrected_daily_sales": 50,
        "corrected_adjustment_decisions": 5, "corrected_royalty_invoices": 8,
        "corrected_food_cost_variance": 190, "corrected_region_daily_sales": 85,
        "corrected_franchisee_invoices": 6,
    }
    for table, expected in expected_counts.items():
        actual = spark.table(f"gold.{table}").count()
        assert actual == expected, f"{table}: expected {expected} source-pack rows, found {actual}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
