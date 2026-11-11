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
# META       "known_lakehouses": [
# META         {
# META           "id": "f8d5782d-d817-44fe-a071-613af0122930",
# META           "name": "lh_polarslice"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Silver: Aloha
# Parses DOB as the business date, preserves post-midnight checks, and exposes tax-exclusive values and mapping quality.

# CELL ********************

batch_id = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark",
# META   "tags": [
# META     "parameters"
# META   ]
# META }

# CELL ********************

import uuid
from pyspark.sql import Window
from pyspark.sql import functions as F

SCHEMA = "silver"
BATCH_ID = batch_id or str(uuid.uuid4())
META = ["_source_system", "_source_file", "_file_modified", "_ingest_ts", "_batch_id"]
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

def parsed(name, data_type):
    return F.expr(f"try_cast(trim(`{name}`) AS {data_type})")

def save(df, table):
    (df.withColumn("_silver_batch_id", F.lit(BATCH_ID))
       .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"{SCHEMA}.{table}"))
    print(f"{SCHEMA}.{table}: {spark.table(f'{SCHEMA}.{table}').count()} rows")

# CELL ********************

checks_raw = spark.table("bronze.aloha_checks")
checks = checks_raw.select(
    parsed("STORE", "INT").alias("store_id"),
    F.to_date("DOB", "yyyyMMdd").alias("business_date"),
    parsed("CHECKID", "INT").alias("check_id"),
    "TABLENUM", "ORDERMODE",
    F.to_timestamp("OPENTIME", "MM/dd/yyyy HH:mm").alias("open_ts"),
    F.to_timestamp("CLOSETIME", "MM/dd/yyyy HH:mm").alias("close_ts"),
    parsed("GROSS", "DECIMAL(12,2)").alias("gross_tax_incl"),
    parsed("COMP", "DECIMAL(12,2)").alias("comp_tax_incl"),
    parsed("NETTOTAL", "DECIMAL(12,2)").alias("net_total_tax_incl"),
    parsed("TAXINCL", "DECIMAL(12,2)").alias("tax"),
    parsed("TIP", "DECIMAL(12,2)").alias("tip"),
    parsed("TOTAL", "DECIMAL(12,2)").alias("total"),
    "PAYTYPE", "EMPLOYEE", *META,
)
checks = (checks
    .withColumn("net_sales_excl_tax", F.col("net_total_tax_incl") - F.col("tax"))
    .withColumn("is_after_midnight", F.to_date("close_ts") > F.col("business_date"))
    .withColumn("is_web_tender", F.col("PAYTYPE") == "WEB")
    .withColumn("check_key", F.concat_ws("|", "store_id", F.date_format("business_date", "yyyyMMdd"), "check_id")))
assert checks.filter(
    F.col("store_id").isNull() | F.col("business_date").isNull() | F.col("check_id").isNull()
    | F.col("open_ts").isNull() | F.col("close_ts").isNull()
    | F.col("gross_tax_incl").isNull() | F.col("comp_tax_incl").isNull()
    | F.col("net_total_tax_incl").isNull() | F.col("tax").isNull()
    | F.col("tip").isNull() | F.col("total").isNull()
).count() == 0
assert checks.filter("is_after_midnight").count() == 131
assert checks.groupBy("store_id", "business_date", "check_id").count().filter("count > 1").count() == 0
assert checks.count() == 2505
save(checks, "aloha_checks")

# CELL ********************

items_raw = spark.table("bronze.aloha_items")
items = items_raw.select(
    parsed("STORE", "INT").alias("store_id"),
    F.to_date("DOB", "yyyyMMdd").alias("business_date"),
    parsed("CHECKID", "INT").alias("check_id"),
    parsed("ENTRYID", "INT").alias("entry_id"),
    "ITEMCODE", "ITEMNAME",
    parsed("QTY", "INT").alias("qty"),
    parsed("PRICE", "DECIMAL(12,2)").alias("unit_price_tax_incl"),
    parsed("AMOUNT", "DECIMAL(12,2)").alias("amount_tax_incl"),
    "TYPE",
    F.to_timestamp("ORDERTIME", "MM/dd/yyyy HH:mm").alias("order_ts"),
    *META,
)
items = items.withColumn(
    "unit_price_excl_tax_est",
    F.round(F.col("unit_price_tax_incl") / F.lit("1.13").cast("DECIMAL(4,2)"), 2)
        .cast("DECIMAL(12,2)"))
menu = spark.table("silver.menu").select(
    F.col("price_excl_tax").alias("_menu_price_excl_tax"), "sku"
)
items = (items.join(
        F.broadcast(menu),
        (F.col("TYPE") == "ITEM") & (F.col("unit_price_excl_tax_est") == F.col("_menu_price_excl_tax")),
        "left")
    .drop("_menu_price_excl_tax")
    .withColumn("is_comp", F.col("TYPE") == "COMP")
    .withColumn("is_item_unmapped", (F.col("TYPE") == "ITEM") & F.col("sku").isNull())
    .withColumn("is_duplicate_line", F.count(F.lit(1)).over(Window.partitionBy(
        "store_id", "business_date", "check_id", "entry_id")) > 1))
assert items.filter(
    F.col("store_id").isNull() | F.col("business_date").isNull() | F.col("check_id").isNull()
    | F.col("entry_id").isNull() | F.col("qty").isNull()
    | F.col("unit_price_tax_incl").isNull() | F.col("amount_tax_incl").isNull()
    | F.col("order_ts").isNull()
).count() == 0
assert items.filter("is_item_unmapped").count() == 0
assert items.count() == 7341
save(items, "aloha_check_lines")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
