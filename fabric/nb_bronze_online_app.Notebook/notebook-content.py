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

# # Bronze: online ordering app
# Loads `orders_*.json` (JSON array per day) and `customers.csv`. Orders are flattened one level into `online_orders` (customer fields inlined) and `online_order_items`; all values stay strings. Cancelled orders and duplicate customer accounts are kept as delivered.

# CELL ********************

batch_id = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import uuid
from pyspark.sql import functions as F

BASE = "Files"
SCHEMA = "bronze"
BATCH_ID = batch_id or str(uuid.uuid4())
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

def with_meta(df, system):
    return (df.withColumn("_source_system", F.lit(system))
              .withColumn("_source_file", F.col("_metadata.file_path"))
              .withColumn("_file_modified", F.col("_metadata.file_modification_time"))
              .withColumn("_ingest_ts", F.current_timestamp())
              .withColumn("_batch_id", F.lit(BATCH_ID)))

def save(df, table):
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"{SCHEMA}.{table}"))
    print(f"{SCHEMA}.{table}: {spark.table(f'{SCHEMA}.{table}').count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

raw = (spark.read.option("multiLine", "true").option("primitivesAsString", "true")
       .json(f"{BASE}/online_app/orders_*.json"))
raw = with_meta(raw, "online_app")
meta_cols = ["_source_system", "_source_file", "_file_modified", "_ingest_ts", "_batch_id"]

orders = raw.select(
    "order_id", "placed_at", "store_id", "channel", "fulfilment", "status", "promo_code",
    F.col("customer.id").alias("customer_id"),
    F.col("customer.name").alias("customer_name"),
    F.col("customer.email").alias("customer_email"),
    F.col("customer.phone").alias("customer_phone"),
    "subtotal", "discount", "tax", "tip", "total", "pos_check_no",
    *meta_cols,
)
save(orders, "online_orders")

items = (raw.select("order_id", F.posexplode("items").alias("line_no", "item"), *meta_cols)
            .select("order_id", (F.col("line_no") + 1).cast("string").alias("line_no"),
                    F.col("item.sku").alias("sku"), F.col("item.name").alias("name"),
                    F.col("item.qty").alias("qty"), F.col("item.unit_price").alias("unit_price"),
                    *meta_cols))
save(items, "online_order_items")

customers = (spark.read.option("header", "true").option("inferSchema", "false")
             .csv(f"{BASE}/online_app/customers.csv"))
save(with_meta(customers, "online_app"), "online_customers")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Expected from the pack: 6 JSON files, 2,268 completed (1,637 MICROS + 631 Aloha) + 34 cancelled orders
o = spark.table("bronze.online_orders")
assert o.select("_source_file").distinct().count() == 6
assert o.filter("status = 'cancelled'").count() == 34
assert o.filter("status = 'completed'").count() == 2268
o.groupBy("status").count().show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
