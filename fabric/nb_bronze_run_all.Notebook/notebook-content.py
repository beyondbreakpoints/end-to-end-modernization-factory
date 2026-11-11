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

# # Bronze: run all
# Runs the five Bronze notebooks with a shared batch id, then prints row counts for every `bronze` table. Upload the files to `Files/` first (see `docs/onelake-upload.md`).

# CELL ********************

import uuid

batch_id = str(uuid.uuid4())
notebooks = ["nb_bronze_master_data", "nb_bronze_micros", "nb_bronze_aloha",
             "nb_bronze_online_app", "nb_bronze_as400_commissary"]
for nb in notebooks:
    print(f"running {nb} (batch {batch_id})")
    notebookutils.notebook.run(nb, 1800, {"batch_id": batch_id, "useRootDefaultLakehouse": True})

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

for t in sorted(r.tableName for r in spark.sql("SHOW TABLES IN bronze").collect()):
    print(f"bronze.{t}: {spark.table('bronze.' + t).count()} rows")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
