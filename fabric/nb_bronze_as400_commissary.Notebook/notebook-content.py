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

# # Bronze: AS/400 commissary
# Fixed-width files sliced by the offsets in the COBOL copybooks (`ITEMREC.CPY` 47, `SHIPREC.CPY` 59, `CNTREC.CPY` 31). Fields are kept as the raw substrings: CYYMMDD dates, implied decimals and trailing signs are decoded in Silver, not here. `_raw_line` keeps the original record.

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

# Copybook layouts: (column, 1-based start, length)
LAYOUTS = {
    "ITEMREC": (47, [("item_code", 1, 8), ("item_desc", 9, 20), ("pack_uom", 29, 2),
                     ("base_uom", 31, 2), ("pack_qty", 33, 7), ("pack_cost", 40, 7),
                     ("status", 47, 1)]),
    "SHIPREC": (59, [("store_no", 1, 5), ("ship_date", 6, 7), ("item_code", 13, 8),
                     ("item_desc", 21, 20), ("qty", 41, 7), ("uom", 48, 2),
                     ("ext_cost", 50, 10)]),
    "CNTREC": (31, [("store_no", 1, 5), ("count_date", 6, 7), ("count_type", 13, 1),
                    ("item_code", 14, 8), ("qty_on_hand", 22, 8), ("base_uom", 30, 2)]),
}

def read_fixed(path, layout):
    length, fields = LAYOUTS[layout]
    df = with_meta(spark.read.text(path), "as400_commissary")
    df = df.filter(F.length("value") > 0)
    bad = df.filter(F.length("value") != length).count()
    assert bad == 0, f"{bad} records in {path} are not {length} chars wide"
    for name, start, size in fields:
        df = df.withColumn(name, F.substring("value", start, size))
    return df.withColumnRenamed("value", "_raw_line")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

save(read_fixed(f"{BASE}/as400_commissary/ITEMMAST.TXT", "ITEMREC"), "as400_itemmast")
save(read_fixed(f"{BASE}/as400_commissary/SHP*.TXT", "SHIPREC"), "as400_shipments")
save(read_fixed(f"{BASE}/as400_commissary/CNT*.TXT", "CNTREC"), "as400_counts")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Expected from the pack: 3 shipment files, 2 count files, 3 credit lines, 9 cheese lines in KG
s = spark.table("bronze.as400_shipments")
assert s.select("_source_file").distinct().count() == 3
assert spark.table("bronze.as400_counts").select("_source_file").distinct().count() == 2
assert s.filter(F.col("ext_cost").endswith("-")).count() == 3
assert s.filter("item_code LIKE 'MOZ%' AND uom = 'KG'").count() == 9

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
