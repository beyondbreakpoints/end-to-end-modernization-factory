# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "ea1119c4-4cf6-49f3-b025-6596594dd487",
# META       "default_lakehouse_name": "lh_polarslice",
# META       "default_lakehouse_workspace_id": "c2e20e29-e252-489b-bd2f-10fb423600eb",
# META       "known_lakehouses": [
# META         {
# META           "id": "ea1119c4-4cf6-49f3-b025-6596594dd487"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Gold: run comparison bridge
# Requires successful legacy and corrected Gold runs. Does not rerun or overwrite any prior milestone.
# Verify the actual default lakehouse item before execution.

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

batch_id = batch_id or str(uuid.uuid4())
print(f"running nb_gold_comparison (batch {batch_id}, period {period_start}..{period_end})")
notebookutils.notebook.run("nb_gold_comparison", 1800, {
    "batch_id": batch_id, "period_start": period_start, "period_end": period_end,
    "useRootDefaultLakehouse": True,
})

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

outputs = [
    "comparison_bridge", "comparison_summary", "comparison_daily", "comparison_invoices",
]
for table in outputs:
    df = spark.table(f"gold.{table}")
    batches = [r[0] for r in df.select("_gold_batch_id").distinct().collect()]
    assert batches == [batch_id], f"gold.{table}: expected batch {batch_id}, found {batches}"
    print(f"gold.{table}: {df.count()} rows, batch={batch_id}")

spark.table("gold.comparison_summary").orderBy("category").show(truncate=False)
spark.table("gold.comparison_daily").orderBy("store_id", "business_date").show(60, truncate=False)
spark.table("gold.comparison_invoices").orderBy("store_id").show(truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
