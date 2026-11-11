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

# # Silver: master data
# Types head-office reference data and validates its natural keys. Raw inputs remain available in Bronze.

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

stores_raw = spark.table("bronze.master_stores")
stores = stores_raw.select(
    parsed("store_id", "INT").alias("store_id"),
    "store_name", "city", "province", "ownership", "franchisee_id", "franchisee_name",
    "pos_system", F.to_date("open_date", "yyyy-MM-dd").alias("open_date"), *META,
)
assert stores.filter(F.col("store_id").isNull() | F.col("open_date").isNull()).count() == 0
assert stores.groupBy("store_id").count().filter("count > 1").count() == 0
save(stores, "stores")

menu_raw = spark.table("bronze.master_menu")
menu = menu_raw.select(
    "sku", "item_name", "category", "size",
    parsed("price_excl_tax", "DECIMAL(12,2)").alias("price_excl_tax"),
    parsed("micros_item_no", "INT").alias("micros_item_no"), *META,
)
assert menu.filter(F.col("price_excl_tax").isNull() | F.col("micros_item_no").isNull()).count() == 0
assert menu.groupBy("sku").count().filter("count > 1").count() == 0
assert menu.groupBy("micros_item_no").count().filter("count > 1").count() == 0
assert menu.select("price_excl_tax").distinct().count() == menu.count()
save(menu, "menu")

calendar_raw = spark.table("bronze.master_calendar")
calendar = calendar_raw.select(
    F.to_date("business_date", "yyyy-MM-dd").alias("business_date"),
    "day_name",
    (F.upper(F.trim("is_2for1_tuesday")) == "Y").alias("is_2for1"),
    *META,
)
assert calendar.filter(F.col("business_date").isNull()).count() == 0
assert calendar.groupBy("business_date").count().filter("count > 1").count() == 0
save(calendar, "calendar")

recipes_raw = spark.table("bronze.master_recipes")
recipes = recipes_raw.select(
    "sku", "ingredient_item_code",
    parsed("qty_per_unit", "DECIMAL(12,3)").alias("qty_per_unit"),
    F.upper(F.trim("base_uom")).alias("base_uom"), *META,
)
assert recipes.filter(F.col("qty_per_unit").isNull()).count() == 0
assert recipes.groupBy("sku", "ingredient_item_code").count().filter("count > 1").count() == 0
save(recipes, "recipes")

# CELL ********************

assert spark.table("silver.stores").count() == 10
assert spark.table("silver.menu").count() == 19
assert spark.table("silver.calendar").count() == 5
assert spark.table("silver.recipes").count() == 62

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
