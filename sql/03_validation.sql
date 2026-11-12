/* =====================================================================================
   Polar Slice Pizza — Corrected Gold Mart  (Azure SQL Database)
   Post-load validation queries. Run after usp_LoadCorrectedGold succeeds.
   All queries should return 0 rows (failures) or the expected value.
   ===================================================================================== */

/* --- Row counts (source pack 2026-03-09..2026-03-13) -------------------------------- */
SELECT 'corrected_run_inputs'           AS tbl, COUNT(*) AS rows, 15   AS expected FROM gold.corrected_run_inputs
UNION ALL
SELECT 'corrected_promo_cost',                  COUNT(*),          69               FROM gold.corrected_promo_cost
UNION ALL
SELECT 'corrected_fact_checks',                 COUNT(*),          9231             FROM gold.corrected_fact_checks
UNION ALL
SELECT 'corrected_fact_check_lines',            COUNT(*),          25664            FROM gold.corrected_fact_check_lines
UNION ALL
SELECT 'corrected_online_attribution',          COUNT(*),          2302             FROM gold.corrected_online_attribution
UNION ALL
SELECT 'corrected_daily_sales',                 COUNT(*),          50               FROM gold.corrected_daily_sales
UNION ALL
SELECT 'corrected_adjustment_decisions',        COUNT(*),          5                FROM gold.corrected_adjustment_decisions
UNION ALL
SELECT 'corrected_royalty_invoices',            COUNT(*),          8                FROM gold.corrected_royalty_invoices
UNION ALL
SELECT 'corrected_food_cost_variance',          COUNT(*),          190              FROM gold.corrected_food_cost_variance
UNION ALL
SELECT 'corrected_region_daily_sales',          COUNT(*),          85               FROM gold.corrected_region_daily_sales
UNION ALL
SELECT 'corrected_franchisee_invoices',         COUNT(*),          6                FROM gold.corrected_franchisee_invoices;
GO

/* --- Period financial totals ------------------------------------------------------- */
SELECT 'net_sales'    AS metric, SUM(net_sales)    AS actual, CAST(268893.08 AS DECIMAL(19,4)) AS expected FROM gold.corrected_daily_sales
UNION ALL
SELECT 'invoice_due',            SUM(amount_due),              17251.74                                    FROM gold.corrected_royalty_invoices;
GO

/* --- Daily net sales --------------------------------------------------------------- */
SELECT business_date, SUM(net_sales) AS net_sales
FROM gold.corrected_daily_sales
GROUP BY business_date
ORDER BY business_date;
GO

/* --- Royalty invoices -------------------------------------------------------------- */
SELECT franchisee_id, franchisee_name, store_id, net_sales, royalty, ad_fund, adjustments, amount_due
FROM gold.corrected_royalty_invoices
ORDER BY franchisee_id, store_id;
GO

/* --- Cheese variance (MOZ00410) ---------------------------------------------------- */
SELECT store_id, item_code, base_uom, opening_qty, received_qty, closing_qty,
       actual_usage, theoretical_usage, variance, variance_pct, variance_cost
FROM gold.corrected_food_cost_variance
WHERE item_code = 'MOZ00410'
ORDER BY store_id;
GO

/* --- Online attribution counts ---------------------------------------------------- */
SELECT attribution_status, COUNT(*) AS check_count
FROM gold.corrected_online_attribution
GROUP BY attribution_status
ORDER BY attribution_status;
GO

/* --- Check balances (gross - discount = net_sales) -------------------------------- */
SELECT COUNT(*) AS unbalanced_checks
FROM gold.corrected_fact_checks
WHERE ABS(gross - discount - net_sales) > 0.01;
GO

/* --- Invoice balance (royalty + ad_fund + adjustments = amount_due) --------------- */
SELECT COUNT(*) AS unbalanced_invoices
FROM gold.corrected_royalty_invoices
WHERE ABS(royalty + ad_fund + adjustments - amount_due) > 0.01;
GO

/* --- No store 1078 invoice (6-month holiday) -------------------------------------- */
SELECT COUNT(*) AS unexpected_1078_invoice
FROM gold.corrected_royalty_invoices
WHERE store_id = 1078;
GO

/* --- Duplicate check keys (should be 0) ------------------------------------------- */
SELECT source_system, check_key, COUNT(*) AS cnt
FROM gold.corrected_fact_checks
GROUP BY source_system, check_key
HAVING COUNT(*) > 1;
GO
