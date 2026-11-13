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
# META     },
# META     "warehouse": {
# META       "known_warehouses": []
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Gold: reference inputs
# Versioned snapshots of SliceDW configuration and finance adjustments, copied from `03_reference_data.sql`.
# Embedded inputs travel with Fabric Git; no additional OneLake upload is required. Legacy mapping defects and both adjustment copies are intentional.

# PARAMETERS CELL ********************

batch_id = ""

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import uuid
from pyspark.sql import Window, functions as F

SCHEMA = "gold"
BATCH_ID = batch_id or str(uuid.uuid4())
REFERENCE_SOURCE = "data/2_legacy_warehouse_slicedw/sql/03_reference_data.sql"
REFERENCE_VERSION = "slicedw-march-2026-v1"
spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

def save(df, table):
    df = (df.withColumn("_reference_source", F.lit(REFERENCE_SOURCE))
          .withColumn("_reference_version", F.lit(REFERENCE_VERSION))
          .withColumn("_gold_batch_id", F.lit(BATCH_ID)))
    (df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"gold.{table}"))
    print(f"gold.{table}: {spark.table(f'gold.{table}').count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

terms = spark.createDataFrame([
    ("ROYALTY_RATE", "0.0500", "Franchise agreement s.7.1"),
    ("AD_FUND_RATE", "0.0300", "Franchise agreement s.7.3"),
    ("NEW_STORE_HOLIDAY_MONTHS", "6.0000",
     "Franchise agreement s.7.5: no royalty or ad fund for the first 6 months"),
], "term_code STRING, term_value STRING, note STRING")
terms = terms.withColumn("term_value", F.col("term_value").cast("DECIMAL(9,4)"))
assert terms.groupBy("term_code").count().filter("count > 1").count() == 0, "Duplicate royalty terms"
save(terms, "reference_royalty_terms")

org = spark.createDataFrame([
    (1, None, "Polar Slice Pizza", "COMPANY", None),
    (10, 1, "Greater Toronto", "REGION", None),
    (20, 1, "Eastern and Central Ontario", "REGION", None),
    (11, 10, "Toronto", "DISTRICT", None),
    (12, 10, "West GTA and Hamilton", "DISTRICT", None),
    (21, 20, "Ottawa and Kingston", "DISTRICT", None),
    (22, 20, "Barrie", "DISTRICT", None),
    (1042, 11, "1042 Queen St West", "STORE", 1042),
    (1043, 11, "1043 Danforth", "STORE", 1043),
    (1055, 12, "1055 Square One", "STORE", 1055),
    (1061, 12, "1061 James St North", "STORE", 1061),
    (1078, 12, "1078 Kerr Village", "STORE", 1078),
    (1090, 12, "1090 Bramalea", "STORE", 1090),
    (3015, 11, "3015 Yonge & Eglinton", "STORE", 3015),
    (2207, 21, "2207 Bank St", "STORE", 2207),
    (2214, 21, "2214 Princess St", "STORE", 2214),
    (2231, 22, "2231 Bayfield", "STORE", 2231),
], "unit_id INT, parent_unit_id INT, unit_name STRING, unit_type STRING, store_id INT")
assert org.groupBy("unit_id").count().filter("count > 1").count() == 0, "Duplicate organization units"
save(org, "reference_org_units")

aloha_map = spark.createDataFrame([
    ("DIPGAR", "SD-DIP"), ("GARBRD", "SD-GARLIC"), ("LGBBQ", "PZ-BBQ-L"),
    ("LGHAW", "PZ-HAW-L"), ("LGMARG", "PZ-MAR-L"), ("LGMEAT", "PZ-MTL-L"),
    ("LGPEP", "PZ-PEP-L"), ("LGVEG", "PZ-VEG-L"), ("MDHAW", "PZ-HAW-M"),
    ("MDMARG", "PZ-MAR-M"), ("MDMEAT", "PZ-MTL-M"), ("MDPEP", "PZ-PEP-M"),
    ("MDVEG", "PZ-VEG-L"), ("POP2L", "BV-POP2L"), ("SMPEP", "PZ-PEP-S"),
], "aloha_item_code STRING, sku STRING")
assert aloha_map.groupBy("aloha_item_code").count().filter("count > 1").count() == 0, \
    "Duplicate legacy Aloha mapping codes"
save(aloha_map, "reference_legacy_aloha_map")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

adjustments = spark.createDataFrame([
    (1, 1042, "2026-03-11", "MARKETING_CREDIT", "-150.00",
     "Local marketing co-op credit, approval M-2231", "jlam", "2026-03-11T16:02:00"),
    (2, 1055, "2026-03-10", "MARKETING_CREDIT", "-120.00",
     "Square One reopening flyer credit", "jlam", "2026-03-10T10:15:00"),
    (3, 2207, "2026-03-12", "EQUIP_RECOVERY", "85.00",
     "Oven repair recharge, ticket 4471", "mpatel", "2026-03-12T14:40:00"),
    (4, 1055, "2026-03-10", "MARKETING_CREDIT", "-120.00",
     "Square One reopening flyer credit", "mpatel", "2026-03-11T09:05:00"),
    (5, 1090, "2026-03-13", "LATE_FEE", "25.00",
     "Late payment fee, February invoice", "jlam", "2026-03-13T11:20:00"),
], "adjustment_id INT, store_id INT, business_date STRING, adj_type STRING, amount STRING, "
   "note STRING, keyed_by STRING, keyed_at STRING")
adjustments = (adjustments
    .withColumn("business_date", F.to_date("business_date", "yyyy-MM-dd"))
    .withColumn("amount", F.col("amount").cast("DECIMAL(19,4)"))
    .withColumn("keyed_at", F.to_timestamp("keyed_at", "yyyy-MM-dd'T'HH:mm:ss"))
    .withColumn("is_possible_duplicate", F.count(F.lit(1)).over(
        Window.partitionBy("store_id", "business_date", "adj_type", "amount", "note")) > 1))
assert adjustments.count() == 5, "Unexpected adjustment snapshot size"
assert adjustments.filter("is_possible_duplicate").count() == 2, \
    "Expected both copies of the Square One marketing credit"
save(adjustments, "reference_manual_adjustments")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
