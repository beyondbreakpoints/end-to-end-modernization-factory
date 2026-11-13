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

# # Bronze: master data (head office)
# Loads `Files/master_data/*.csv` as raw all-string Delta tables in `bronze`, plus load metadata. No typing or cleaning here.

# CELL ********************

# Parameter cell: nb_bronze_run_all passes one batch id to every notebook
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
    # must be applied directly on the file read: _metadata is dropped by later selects
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

tables = {
    "stores": "master_stores",
    "menu": "master_menu",
    "calendar": "master_calendar",
    "recipes": "master_recipes",
}
for file_stem, table in tables.items():
    df = (spark.read.option("header", "true").option("inferSchema", "false")
          .csv(f"{BASE}/master_data/{file_stem}.csv"))
    save(with_meta(df, "master_data"), table)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Expected from the pack: 10 stores, 5 calendar days
assert spark.table("bronze.master_stores").count() == 10
assert spark.table("bronze.master_calendar").count() == 5

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
