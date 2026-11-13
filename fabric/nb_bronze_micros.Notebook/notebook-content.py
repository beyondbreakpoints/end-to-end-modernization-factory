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

# # Bronze: MICROS tills
# Loads pipe-delimited `check_header_*.txt` and `check_detail_*.txt` as raw all-string tables. Gift loads, post-close voids, duplicate checks and online refs are kept exactly as delivered.

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

def read_micros(prefix):
    df = (spark.read.option("header", "true").option("sep", "|").option("inferSchema", "false")
          .csv(f"{BASE}/micros/{prefix}_*.txt"))
    return with_meta(df, "micros")

save(read_micros("check_header"), "micros_check_header")
save(read_micros("check_detail"), "micros_check_detail")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Expected from the pack: 5 daily files each; 49 gift checks, 14 post-close voids
h = spark.table("bronze.micros_check_header")
assert h.select("_source_file").distinct().count() == 5
assert spark.table("bronze.micros_check_detail").select("_source_file").distinct().count() == 5
assert h.filter("order_type = 'GIFT'").count() == 49
assert h.filter("void_flag = 'V'").count() == 14
h.groupBy("store").count().orderBy("store").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
