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

# # Silver: run all
# Runs the five Silver notebooks after Bronze, sharing one batch ID. Online/POS matching runs after both till transformations.

# CELL ********************

import uuid

batch_id = str(uuid.uuid4())
notebooks = [
    "nb_silver_master_data",
    "nb_silver_micros",
    "nb_silver_aloha",
    "nb_silver_as400_commissary",
    "nb_silver_online_app",
]
for nb in notebooks:
    print(f"running {nb} (batch {batch_id})")
    notebookutils.notebook.run(
        nb, 1800, {"batch_id": batch_id, "useRootDefaultLakehouse": True})

# CELL ********************

expected_tables = [
    "stores", "menu", "calendar", "recipes",
    "micros_checks", "micros_check_lines",
    "aloha_checks", "aloha_check_lines",
    "as400_item_master", "as400_shipments", "as400_stock_counts",
    "online_orders", "online_order_items", "online_customers",
]
batch_mismatches = []
for table in expected_tables:
    batches = [row[0] for row in spark.table(f"silver.{table}")
               .select("_silver_batch_id").distinct().collect()]
    print(f"silver.{table}: batches={batches}, expected={batch_id}")
    if batches != [batch_id]:
        batch_mismatches.append((table, batches))
assert not batch_mismatches, \
    f"Silver runner batch {batch_id} was not written to all outputs: {batch_mismatches}. Check child parameter cells and default lakehouse."

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

for table in sorted(row.tableName for row in spark.sql("SHOW TABLES IN silver").collect()):
    print(f"silver.{table}: {spark.table(f'silver.{table}').count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
