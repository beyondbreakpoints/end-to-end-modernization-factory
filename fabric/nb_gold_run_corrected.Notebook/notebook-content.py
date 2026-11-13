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
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Gold: run corrected milestone
# Requires successful Silver and the existing Gold reference snapshots. Does not rerun or overwrite legacy/reference notebooks.
# Verify the actual default lakehouse item, not just its name, before execution.

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
print(f"running nb_gold_corrected (batch {batch_id}, period {period_start}..{period_end})")
notebookutils.notebook.run("nb_gold_corrected", 1800, {
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
    "corrected_run_inputs", "corrected_promo_cost", "corrected_fact_checks",
    "corrected_fact_check_lines", "corrected_online_attribution", "corrected_daily_sales",
    "corrected_adjustment_decisions", "corrected_royalty_invoices",
    "corrected_food_cost_variance", "corrected_region_daily_sales", "corrected_franchisee_invoices",
]
for table in outputs:
    df = spark.table(f"gold.{table}")
    batches = [r[0] for r in df.select("_gold_batch_id").distinct().collect()]
    assert batches == [batch_id], f"gold.{table}: expected runner batch {batch_id}, found {batches}"
    print(f"gold.{table}: {df.count()} rows, batch={batch_id}")
spark.table("gold.corrected_daily_sales").groupBy("business_date").sum("net_sales").orderBy("business_date").show()
spark.table("gold.corrected_royalty_invoices").orderBy("franchisee_id", "store_id").show(truncate=False)
spark.table("gold.corrected_food_cost_variance").filter("item_code = 'MOZ00410'").orderBy("store_id").show(truncate=False)
spark.table("gold.corrected_online_attribution").groupBy("attribution_status").count().orderBy("attribution_status").show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
