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
# META           "id": "f8d5782d-d817-44fe-a071-613af0122930"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Bronze: Aloha tills
# Loads `aloha/<store>/<yyyymmdd>/CHECKS.csv` and `ITEMS.csv` as raw all-string tables. Amounts stay tax-inclusive and DOB is untouched. Store and folder date are also derived from the file path for lineage.

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

BASE = "Files/polar_slice"
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

def read_aloha(file_name):
    df = (spark.read.option("header", "true").option("inferSchema", "false")
          .csv(f"{BASE}/aloha/*/*/{file_name}"))
    df = with_meta(df, "aloha")
    return (df.withColumn("_path_store", F.regexp_extract("_source_file", r"/aloha/(\d+)/(\d{8})/", 1))
              .withColumn("_path_dob", F.regexp_extract("_source_file", r"/aloha/(\d+)/(\d{8})/", 2)))

save(read_aloha("CHECKS.csv"), "aloha_checks")
save(read_aloha("ITEMS.csv"), "aloha_items")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Expected from the pack: 3 stores x 5 days = 15 folders, 2,505 checks
c = spark.table("bronze.aloha_checks")
assert c.select("_source_file").distinct().count() == 15
assert c.count() == 2505
assert spark.table("bronze.aloha_items").select("_source_file").distinct().count() == 15
c.groupBy("STORE").count().orderBy("STORE").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
