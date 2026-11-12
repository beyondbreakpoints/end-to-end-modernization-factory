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

# # Silver: MICROS
# Casts check headers and lines, maps known item numbers, and marks anomalies without removing records.

# PARAMETERS CELL ********************

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

headers_raw = spark.table("bronze.micros_check_header")
headers = headers_raw.select(
    parsed("store", "INT").alias("store_id"),
    F.to_date("business_date", "yyyy-MM-dd").alias("business_date"),
    parsed("check_no", "INT").alias("check_no"),
    "open_time", "close_time", "order_type",
    parsed("guest_count", "INT").alias("guest_count"),
    parsed("subtotal", "DECIMAL(12,2)").alias("subtotal"),
    parsed("discount", "DECIMAL(12,2)").alias("discount"),
    parsed("tax", "DECIMAL(12,2)").alias("tax"),
    parsed("tip", "DECIMAL(12,2)").alias("tip"),
    parsed("total", "DECIMAL(12,2)").alias("total"),
    "tender", "void_flag",
    F.when(F.length(F.trim("online_ref")) > 0, F.trim("online_ref")).alias("online_ref"),
    "employee_id", *META,
)
headers = (headers
    .withColumn("open_ts", F.to_timestamp(F.concat_ws(" ", F.col("business_date").cast("string"), "open_time"),
                                          "yyyy-MM-dd HH:mm:ss"))
    .withColumn("close_ts_local", F.to_timestamp(F.concat_ws(" ", F.col("business_date").cast("string"), "close_time"),
                                                 "yyyy-MM-dd HH:mm:ss"))
    .withColumn("close_ts", F.when(F.col("close_ts_local") < F.col("open_ts"),
                                  F.expr("close_ts_local + INTERVAL 1 DAY"))
                              .otherwise(F.col("close_ts_local")))
    .drop("close_ts_local"))
header_key = Window.partitionBy("store_id", "business_date", "check_no", "void_flag")
headers = (headers
    .withColumn("_same_version_count", F.count(F.lit(1)).over(header_key))
    .withColumn("is_duplicate_check", F.col("_same_version_count") > 1)
    .withColumn("is_gift_check", F.col("order_type") == "GIFT")
    .withColumn("is_void_reversal", F.col("void_flag") == "V")
    .withColumn("is_post_close_void",
                (F.col("void_flag") == "V") & (F.col("close_time") > F.lit("23:50:00")))
    .withColumn("has_online_ref", F.col("online_ref").isNotNull())
    .drop("_same_version_count"))

assert headers.filter(
    F.col("store_id").isNull() | F.col("business_date").isNull() | F.col("check_no").isNull()
    | F.col("subtotal").isNull() | F.col("discount").isNull() | F.col("tax").isNull()
    | F.col("tip").isNull() | F.col("total").isNull()
).count() == 0
assert headers.filter("is_gift_check").count() == 49
assert headers.filter("is_void_reversal").count() == 14
assert headers.filter("is_post_close_void").count() == 14
assert headers.filter("is_duplicate_check").count() == 24
assert headers.count() == 6815
save(headers, "micros_checks")

# CELL ********************

details_raw = spark.table("bronze.micros_check_detail")
details = details_raw.select(
    parsed("store", "INT").alias("store_id"),
    F.to_date("business_date", "yyyy-MM-dd").alias("business_date"),
    parsed("check_no", "INT").alias("check_no"),
    parsed("line_no", "INT").alias("line_no"),
    parsed("item_no", "INT").alias("item_no"),
    "item_name",
    parsed("qty", "INT").alias("qty"),
    parsed("unit_price", "DECIMAL(12,2)").alias("unit_price"),
    parsed("line_amount", "DECIMAL(12,2)").alias("line_amount"),
    "line_type", *META,
)
menu = spark.table("silver.menu").select(
    F.col("micros_item_no").alias("_menu_item_no"), "sku"
)
details = (details.join(F.broadcast(menu), details.item_no == menu._menu_item_no, "left")
    .drop("_menu_item_no")
    .withColumn("is_duplicate_line",
                F.count(F.lit(1)).over(Window.partitionBy(
                    "store_id", "business_date", "check_no", "line_no")) > 1)
    .withColumn("is_gift_line", F.col("line_type") == "GIFT")
    .withColumn("is_discount_line", F.col("line_type") == "DISC")
    .withColumn("is_void_line", F.col("line_type") == "VOID")
    .withColumn("is_item_unmapped", (F.col("line_type") == "ITEM") & F.col("sku").isNull()))
assert details.filter(
    F.col("store_id").isNull() | F.col("business_date").isNull() | F.col("check_no").isNull()
    | F.col("line_no").isNull() | F.col("qty").isNull() | F.col("unit_price").isNull()
    | F.col("line_amount").isNull()
).count() == 0
assert details.count() == 19880
save(details, "micros_check_lines")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
