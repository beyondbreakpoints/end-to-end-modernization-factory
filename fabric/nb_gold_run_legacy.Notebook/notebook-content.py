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
# META       "default_lakehouse_workspace_id": "",
# META       "known_lakehouses": [
# META         {
# META           "id": "767bc30b-8fb4-4c88-9725-7632324e8d58"
# META         }
# META       ]
# META     },
# META     "warehouse": {
# META       "known_warehouses": []
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Gold: run legacy milestone
# Run after a successful Silver runner batch. This runner does not execute corrected Gold or answer-key reconciliation.

# PARAMETERS CELL ********************

batch_id = ""
period_start = "2026-03-09"
period_end = "2026-03-13"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import uuid
from datetime import date

assert date.fromisoformat(period_start) <= date.fromisoformat(period_end), "Invalid reporting period"
batch_id = batch_id or str(uuid.uuid4())
for nb in ["nb_gold_reference_data", "nb_gold_legacy"]:
    print(f"running {nb} (batch {batch_id}, period {period_start}..{period_end})")
    arguments = {"batch_id": batch_id, "useRootDefaultLakehouse": True}
    if nb == "nb_gold_legacy":
        arguments.update({"period_start": period_start, "period_end": period_end})
    notebookutils.notebook.run(nb, 1800, arguments)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

for row in spark.sql("SHOW TABLES IN gold").collect():
    if row.tableName.startswith(("reference_", "legacy_")):
        print(f"gold.{row.tableName}: {spark.table('gold.' + row.tableName).count()} rows")
spark.table("gold.legacy_daily_sales").groupBy("business_date").sum("net_sales").orderBy("business_date").show()
spark.table("gold.legacy_royalty_invoices").orderBy("franchisee_id", "store_id").show(truncate=False)
spark.table("gold.legacy_food_cost_variance").filter("item_code = 'MOZ00410'").orderBy("store_id").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
