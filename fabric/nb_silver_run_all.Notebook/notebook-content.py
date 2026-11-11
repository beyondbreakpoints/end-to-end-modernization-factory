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

for table in sorted(row.tableName for row in spark.sql("SHOW TABLES IN silver").collect()):
    print(f"silver.{table}: {spark.table(f'silver.{table}').count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
