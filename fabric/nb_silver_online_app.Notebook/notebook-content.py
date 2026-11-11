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

# # Silver: online app
# Parses order/customer data, preserves cancellations and possible duplicate accounts, and links completed orders to POS records.
# MICROS links use `online_ref`; Aloha candidates require the same store/business date, total within one cent, and opening time within two minutes.

# CELL ********************

batch_id = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
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

orders_raw = spark.table("bronze.online_orders")
orders = orders_raw.select(
    "order_id",
    F.to_timestamp("placed_at").alias("placed_at"),
    F.to_timestamp(F.substring("placed_at", 1, 19), "yyyy-MM-dd'T'HH:mm:ss")
        .alias("placed_local_ts"),
    F.to_date(F.substring("placed_at", 1, 10), "yyyy-MM-dd").alias("_placed_local_date"),
    F.substring("placed_at", 12, 2).cast("INT").alias("_placed_local_hour"),
    parsed("store_id", "INT").alias("store_id"),
    "channel", "fulfilment", "status", "promo_code",
    parsed("customer_id", "INT").alias("customer_id"),
    "customer_name", "customer_email", "customer_phone",
    parsed("subtotal", "DECIMAL(12,2)").alias("subtotal"),
    parsed("discount", "DECIMAL(12,2)").alias("discount"),
    parsed("tax", "DECIMAL(12,2)").alias("tax"),
    parsed("tip", "DECIMAL(12,2)").alias("tip"),
    parsed("total", "DECIMAL(12,2)").alias("total"),
    parsed("pos_check_no", "INT").alias("pos_check_no"), *META,
)
orders = (orders
    .withColumn("business_date",
        F.when(F.col("_placed_local_hour") < 4, F.date_sub("_placed_local_date", 1))
         .otherwise(F.col("_placed_local_date")))
    .withColumn("is_completed", F.lower("status") == "completed")
    .withColumn("is_cancelled", F.lower("status") == "cancelled")
    .withColumn("has_pos_check_no", F.col("pos_check_no").isNotNull())
    .drop("_placed_local_date", "_placed_local_hour"))
assert orders.filter(
    F.col("order_id").isNull() | F.col("placed_at").isNull() | F.col("business_date").isNull()
    | F.col("store_id").isNull() | F.col("total").isNull()
).count() == 0
assert orders.filter("is_cancelled").count() == 34
assert orders.filter("is_completed").count() == 2268

# CELL ********************

micros_refs = (spark.table("silver.micros_checks")
    .filter(F.col("online_ref").isNotNull())
    .select(F.col("store_id").alias("micros_store_id"),
            F.col("online_ref").alias("micros_order_id"), "business_date", "check_no")
    .distinct()
    .groupBy("micros_store_id", "micros_order_id")
    .agg(F.count(F.lit(1)).alias("micros_candidate_count"),
         F.first("business_date").alias("micros_business_date"),
         F.first("check_no").alias("micros_check_no")))
aloha = (spark.table("silver.aloha_checks")
    .select("store_id", "business_date", "check_key", "open_ts", "total")
    .distinct())

o = orders.filter(
    (F.col("status") == "completed") & F.col("pos_check_no").isNull()
).alias("o")
a = aloha.alias("a")
time_delta = F.abs(F.unix_timestamp(F.col("o.placed_local_ts")) -
                   F.unix_timestamp(F.col("a.open_ts")))
amount_delta = F.abs(F.col("o.total") - F.col("a.total"))
candidates = (o.join(
        a,
        (F.col("o.store_id") == F.col("a.store_id"))
        & (F.col("o.business_date") == F.col("a.business_date"))
        & (time_delta <= 120)
        & (amount_delta <= F.lit("0.01").cast("DECIMAL(3,2)")),
        "inner")
    .select(F.col("o.order_id").alias("order_id"),
            F.col("a.check_key").alias("aloha_check_key"),
            time_delta.alias("time_delta_seconds")))
candidate_counts = candidates.groupBy("order_id").agg(
    F.count(F.lit(1)).alias("aloha_candidate_count"))
nearest_window = Window.partitionBy("order_id").orderBy(F.col("time_delta_seconds"))
nearest = (candidates
    .withColumn("_rank", F.dense_rank().over(nearest_window))
    .filter(F.col("_rank") == 1)
    .groupBy("order_id")
    .agg(F.count(F.lit(1)).alias("aloha_best_tie_count"),
         F.first("aloha_check_key").alias("aloha_check_key"),
         F.min("time_delta_seconds").alias("aloha_time_delta_seconds")))
aloha_matches = candidate_counts.join(nearest, "order_id", "inner")

orders_matched = (orders
    .join(micros_refs,
          (F.col("store_id") == F.col("micros_store_id"))
          & (F.col("order_id") == F.col("micros_order_id")), "left")
    .join(aloha_matches.alias("a"), "order_id", "left")
    .withColumn("pos_match_status",
        F.when(~F.col("is_completed"), "CANCELLED")
         .when(F.col("micros_candidate_count") == 1, "MATCHED_MICROS")
         .when(F.col("micros_candidate_count") > 1, "AMBIGUOUS_MICROS")
         .when(F.col("store_id").isin(2207, 2214, 2231)
               & (F.col("aloha_best_tie_count") == 1), "MATCHED_ALOHA")
         .when(F.col("store_id").isin(2207, 2214, 2231)
               & (F.col("aloha_best_tie_count") > 1), "AMBIGUOUS_ALOHA")
         .otherwise("UNMATCHED"))
    .withColumn("pos_match_system",
        F.when(F.col("micros_candidate_count") > 0, "MICROS")
         .when(F.col("aloha_candidate_count") > 0, "ALOHA"))
    .withColumn("pos_match_check_key",
        F.when(F.col("micros_candidate_count") == 1,
               F.concat_ws("|", F.col("store_id"),
                           F.date_format("micros_business_date", "yyyyMMdd"),
                           F.col("micros_check_no")))
         .when(F.col("aloha_best_tie_count") == 1, F.col("aloha_check_key")))
    .withColumn("pos_match_candidate_count",
        F.when(F.col("micros_candidate_count").isNotNull(), F.col("micros_candidate_count"))
         .otherwise(F.coalesce(F.col("aloha_candidate_count"), F.lit(0))))
    .withColumn("pos_match_best_tie_count",
        F.when(F.col("micros_candidate_count").isNotNull(), F.col("micros_candidate_count"))
         .otherwise(F.coalesce(F.col("aloha_best_tie_count"), F.lit(0))))
    .withColumn("pos_match_time_delta_seconds", F.col("aloha_time_delta_seconds"))
    .drop("micros_store_id", "micros_order_id", "micros_candidate_count", "micros_business_date",
          "micros_check_no", "aloha_candidate_count", "aloha_best_tie_count",
          "aloha_check_key", "aloha_time_delta_seconds"))

assert orders_matched.filter("pos_match_status = 'MATCHED_MICROS'").count() == 1637
assert orders_matched.filter("pos_match_status = 'MATCHED_ALOHA'").count() == 630
assert orders_matched.filter("pos_match_status = 'AMBIGUOUS_ALOHA'").count() == 1
assert orders_matched.count() == 2302
save(orders_matched, "online_orders")

# CELL ********************

items_raw = spark.table("bronze.online_order_items")
order_items = items_raw.select(
    "order_id",
    parsed("line_no", "INT").alias("line_no"),
    "sku", F.col("name").alias("item_name"),
    parsed("qty", "INT").alias("qty"),
    parsed("unit_price", "DECIMAL(12,2)").alias("unit_price"), *META,
)
menu_skus = F.broadcast(spark.table("silver.menu").select(F.col("sku").alias("_menu_sku")).distinct())
order_items = (order_items
    .join(menu_skus, F.col("sku") == F.col("_menu_sku"), "left")
    .withColumn("is_item_unmapped", F.col("_menu_sku").isNull())
    .drop("_menu_sku"))
assert order_items.filter(F.col("line_no").isNull() | F.col("qty").isNull()
                          | F.col("unit_price").isNull()).count() == 0
assert order_items.filter("is_item_unmapped").count() == 0
assert order_items.count() == 6398
save(order_items, "online_order_items")

# CELL ********************

customers_raw = spark.table("bronze.online_customers")
customers = customers_raw.select(
    parsed("customer_id", "INT").alias("customer_id"),
    "full_name", "email", "phone",
    F.to_timestamp("created_at", "yyyy-MM-dd HH:mm:ss").alias("created_at"),
    parsed("home_store_id", "INT").alias("home_store_id"),
    parsed("loyalty_points", "INT").alias("loyalty_points"),
    (F.trim("marketing_opt_in") == "1").alias("marketing_opt_in"), *META,
)
customers = (customers
    .withColumn("_phone_digits", F.regexp_replace(F.col("phone"), "[^0-9]", ""))
    .withColumn("normalized_phone",
        F.when((F.length("_phone_digits") == 11) & F.col("_phone_digits").startswith("1"),
               F.substring("_phone_digits", 2, 10))
         .when(F.length("_phone_digits") == 10, F.col("_phone_digits")))
    .withColumn("normalized_name",
        F.lower(F.regexp_replace(F.trim("full_name"), "[^A-Za-z0-9]", "")))
    .withColumn("possible_duplicate_by_phone",
        F.when(F.col("normalized_phone").isNotNull(),
               F.count(F.lit(1)).over(Window.partitionBy("normalized_phone")) > 1)
         .otherwise(F.lit(False)))
    .withColumn("possible_duplicate_by_name",
        F.count(F.lit(1)).over(Window.partitionBy("normalized_name")) > 1)
    .withColumn("is_possible_duplicate",
        F.col("possible_duplicate_by_phone") | F.col("possible_duplicate_by_name"))
    .drop("_phone_digits"))
assert customers.filter(F.col("customer_id").isNull() | F.col("created_at").isNull()).count() == 0
assert customers.groupBy("customer_id").count().filter("count > 1").count() == 0
assert customers.filter("possible_duplicate_by_phone").count() == 290
assert customers.count() == 1489
save(customers, "online_customers")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
