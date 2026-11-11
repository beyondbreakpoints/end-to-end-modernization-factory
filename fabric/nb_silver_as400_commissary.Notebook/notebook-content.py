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

# # Silver: AS/400 commissary
# Decodes CYYMMDD dates and implied decimals, applies trailing credit signs, and normalizes shipment quantities to item base units.

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
from pyspark.sql import functions as F

SCHEMA = "silver"
BATCH_ID = batch_id or str(uuid.uuid4())
META = ["_source_system", "_source_file", "_file_modified", "_ingest_ts", "_batch_id"]
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

def parsed(name, data_type):
    return F.expr(f"try_cast(trim(`{name}`) AS {data_type})")

def cyymmdd(name):
    raw = F.trim(F.col(name))
    return F.when(
        F.substring(raw, 1, 1) == "1",
        F.to_date(F.concat(
            F.lit("20"), F.substring(raw, 2, 2), F.lit("-"),
            F.substring(raw, 4, 2), F.lit("-"), F.substring(raw, 6, 2)),
            "yyyy-MM-dd"))

def save(df, table):
    (df.withColumn("_silver_batch_id", F.lit(BATCH_ID))
       .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"{SCHEMA}.{table}"))
    print(f"{SCHEMA}.{table}: {spark.table(f'{SCHEMA}.{table}').count()} rows")

# CELL ********************

items_raw = spark.table("bronze.as400_itemmast")
items = items_raw.select(
    F.trim("item_code").alias("item_code"),
    F.trim("item_desc").alias("item_desc"),
    F.upper(F.trim("pack_uom")).alias("pack_uom"),
    F.upper(F.trim("base_uom")).alias("base_uom"),
    (parsed("pack_qty", "DECIMAL(12,0)") / F.lit(1000)).cast("DECIMAL(12,3)").alias("pack_qty"),
    (parsed("pack_cost", "DECIMAL(12,0)") / F.lit(100)).cast("DECIMAL(12,2)").alias("pack_cost"),
    F.trim("status").alias("status"), *META,
)
assert items.filter(F.col("pack_qty").isNull() | F.col("pack_cost").isNull()).count() == 0
assert items.groupBy("item_code").count().filter("count > 1").count() == 0
assert items.count() == 19
save(items, "as400_item_master")

# CELL ********************

shipments_raw = spark.table("bronze.as400_shipments")
shipments = shipments_raw.select(
    parsed("store_no", "INT").alias("store_id"),
    cyymmdd("ship_date").alias("ship_date"),
    F.trim("item_code").alias("item_code"),
    F.trim("item_desc").alias("item_desc"),
    (parsed("qty", "DECIMAL(12,0)") / F.lit(100)).cast("DECIMAL(12,2)").alias("quantity"),
    F.upper(F.trim("uom")).alias("uom"),
    F.trim("ext_cost").alias("ext_cost_raw"), *META,
)
shipments = (shipments
    .withColumn("_cost_magnitude",
                (F.expr("try_cast(substring(ext_cost_raw, 1, 9) AS DECIMAL(12,0))")
                 / F.lit(100)).cast("DECIMAL(12,2)"))
    .withColumn("is_credit", F.substring("ext_cost_raw", 10, 1) == "-")
    .withColumn("ext_cost", F.when(F.col("is_credit"), -F.col("_cost_magnitude"))
                             .otherwise(F.col("_cost_magnitude")))
    .drop("_cost_magnitude"))
item_units = spark.table("silver.as400_item_master").select(
    "item_code", "pack_uom", "base_uom", "pack_qty")
shipments = (shipments.join(F.broadcast(item_units), "item_code", "left")
    .withColumn("quantity_base_units",
        F.when(F.col("uom") == F.col("base_uom"), F.col("quantity"))
         .when(F.col("uom") == F.col("pack_uom"), F.col("quantity") * F.col("pack_qty"))
         .otherwise(F.lit(None).cast("DECIMAL(18,3)"))
         .cast("DECIMAL(18,3)"))
    .withColumn("quantity_base_units",
        F.when(F.col("is_credit"), -F.col("quantity_base_units"))
         .otherwise(F.col("quantity_base_units")))
    .withColumn("base_uom", F.col("base_uom"))
    .withColumn("has_known_uom", F.col("quantity_base_units").isNotNull()))
assert shipments.filter(
    F.col("store_id").isNull() | F.col("ship_date").isNull() | F.col("quantity").isNull()
    | F.col("ext_cost").isNull()
).count() == 0
assert shipments.filter("is_credit").count() == 3
assert shipments.filter("item_code LIKE 'MOZ%' AND uom = 'KG'").count() == 9
assert shipments.filter(F.col("quantity_base_units").isNull()).count() == 0
assert shipments.count() == 564
save(shipments, "as400_shipments")

# CELL ********************

counts_raw = spark.table("bronze.as400_counts")
counts = counts_raw.select(
    parsed("store_no", "INT").alias("store_id"),
    cyymmdd("count_date").alias("count_date"),
    F.trim("count_type").alias("count_type"),
    F.trim("item_code").alias("item_code"),
    (parsed("qty_on_hand", "DECIMAL(12,0)") / F.lit(1000))
        .cast("DECIMAL(12,3)").alias("quantity_on_hand"),
    F.upper(F.trim("base_uom")).alias("base_uom"), *META,
)
assert counts.filter(
    F.col("store_id").isNull() | F.col("count_date").isNull()
    | F.col("quantity_on_hand").isNull()
).count() == 0
assert counts.filter(~F.col("count_type").isin("O", "C")).count() == 0
assert counts.count() == 380
save(counts, "as400_stock_counts")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
